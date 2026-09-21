//! Experimental required-input executor; accepts only IR validated by the harness.
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    collections::{BTreeMap, BTreeSet},
    error::Error,
    sync::Arc,
};
use tokio::{
    io::{AsyncReadExt, AsyncWriteExt},
    net::{UnixListener, UnixStream},
    process::{Child, Command},
    sync::Mutex,
    task::JoinSet,
};

type Result<T> = std::result::Result<T, Box<dyn Error + Send + Sync>>;
const MAX_FRAME: usize = 16 * 1024 * 1024;

fn now() -> u64 {
    let mut ts = libc::timespec {
        tv_sec: 0,
        tv_nsec: 0,
    };
    // Same Linux CLOCK_MONOTONIC domain as Python's monotonic_ns.
    assert_eq!(
        unsafe { libc::clock_gettime(libc::CLOCK_MONOTONIC, &mut ts) },
        0
    );
    ts.tv_sec as u64 * 1_000_000_000 + ts.tv_nsec as u64
}

async fn read(stream: &mut UnixStream) -> Result<Value> {
    let n = stream.read_u32().await? as usize;
    if n > MAX_FRAME {
        return Err("frame exceeds 16 MiB".into());
    }
    let mut bytes = vec![0; n];
    stream.read_exact(&mut bytes).await?;
    Ok(serde_json::from_slice(&bytes)?)
}

async fn write(stream: &mut UnixStream, value: &Value) -> Result<()> {
    let bytes = serde_json::to_vec(value)?;
    if bytes.len() > MAX_FRAME {
        return Err("frame exceeds 16 MiB".into());
    }
    stream.write_u32(bytes.len() as u32).await?;
    stream.write_all(&bytes).await?;
    Ok(())
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Node {
    id: String,
    control_preconditions: Vec<String>,
    input_bindings: Value,
    executable: String,
}

fn resolve(value: &Value, outputs: &BTreeMap<String, Value>) -> Result<Value> {
    match value {
        Value::Object(o) if o.len() == 1 && o.contains_key("$ref") => {
            let path = o["$ref"].as_str().ok_or("invalid ref")?;
            let mut parts = path.split('.');
            let head = parts.next().ok_or("empty ref")?;
            let mut v = outputs.get(head).ok_or("required input not available")?;
            for part in parts {
                v = if let Value::Array(a) = v {
                    a.get(part.parse::<usize>()?)
                        .ok_or("array ref out of range")?
                } else {
                    v.get(part).ok_or("missing bound field")?
                };
            }
            Ok(v.clone())
        }
        Value::Object(o) => Ok(Value::Object(
            o.iter()
                .map(|(k, v)| Ok((k.clone(), resolve(v, outputs)?)))
                .collect::<Result<_>>()?,
        )),
        Value::Array(a) => Ok(Value::Array(
            a.iter()
                .map(|v| resolve(v, outputs))
                .collect::<Result<_>>()?,
        )),
        _ => Ok(value.clone()),
    }
}

fn validate(nodes: &[Node]) -> Result<()> {
    let ids: BTreeSet<_> = nodes.iter().map(|n| n.id.clone()).collect();
    if ids.len() != nodes.len() || nodes.is_empty() || nodes.len() > 64 {
        return Err("invalid node IDs/count".into());
    }
    for n in nodes {
        if n.id == "in"
            || ![
                "bench.prepare",
                "bench.decision",
                "bench.proposal",
                "bench.identity",
                "noop",
                "end",
            ]
            .contains(&n.executable.as_str())
        {
            return Err("unsupported executable/ID".into());
        }
        if n.control_preconditions
            .iter()
            .any(|p| !ids.contains(p) || p == &n.id)
        {
            return Err("invalid control prerequisite".into());
        }
    }
    let mut complete = BTreeSet::new();
    loop {
        let before = complete.len();
        for n in nodes {
            if n.control_preconditions.iter().all(|p| complete.contains(p)) {
                complete.insert(n.id.clone());
            }
        }
        if complete.len() == nodes.len() {
            return Ok(());
        }
        if complete.len() == before {
            return Err("cyclic controls".into());
        }
    }
}

async fn execute(request: Value, workers: &[Arc<Mutex<UnixStream>>]) -> Result<Value> {
    let nodes: Vec<Node> = serde_json::from_value(request["nodes"].clone())?;
    validate(&nodes)?;
    let start = now();
    let mut outputs = BTreeMap::from([("in".to_string(), json!({"state":request["state"]}))]);
    let mut finished = BTreeMap::from([("in".to_string(), start)]);
    let mut launched = BTreeSet::new();
    let mut running = JoinSet::new();
    let mut available: Vec<usize> = (0..workers.len()).collect();
    let mut events = Vec::new();
    while launched.len() < nodes.len() || !running.is_empty() {
        let before = launched.len();
        for n in &nodes {
            if launched.contains(&n.id) || available.is_empty() {
                continue;
            }
            if !n
                .control_preconditions
                .iter()
                .all(|p| outputs.contains_key(p))
            {
                continue;
            }
            let Ok(inputs) = resolve(&n.input_bindings, &outputs) else {
                continue;
            };
            let eligible = n
                .control_preconditions
                .iter()
                .map(|p| finished[p])
                .max()
                .unwrap_or(start);
            let dispatch = now();
            launched.insert(n.id.clone());
            if n.executable == "noop" || n.executable == "end" {
                outputs.insert(n.id.clone(), json!({}));
                finished.insert(n.id.clone(), dispatch);
                continue;
            }
            let index = available.pop().ok_or("no worker")?;
            let worker = workers[index].clone();
            let n = n.clone();
            let invocation = request["execution_id"].clone();
            running.spawn(async move {
                let mut stream=worker.lock().await;
                write(&mut stream,&json!({"tool":n.executable,"inputs":inputs,"node":n.id,"execution_id":invocation})).await?;
                let response=read(&mut stream).await?;
                if response["ok"]!=true { return Err(format!("worker failed: {}", response["error_type"]).into()); }
                let event=json!({"node":n.id,"inputs":inputs,"output":response["output"],
                    "eligible_ns":eligible,"dispatch_ns":dispatch,
                    "worker_start_ns":response["start_ns"],"worker_end_ns":response["end_ns"],"received_ns":now()});
                Ok::<_,Box<dyn Error+Send+Sync>>((index,n.id,response["output"].clone(),event))
            });
        }
        if running.is_empty() {
            if launched.len() > before && launched.len() < nodes.len() {
                continue;
            }
            if launched.len() != nodes.len() {
                return Err("unresolved required inputs".into());
            }
            break;
        }
        let (index, id, output, event) = running.join_next().await.ok_or("lost task")???;
        available.push(index);
        finished.insert(id.clone(), now());
        outputs.insert(id, output);
        events.push(event);
    }
    Ok(json!({"ok":true,"outputs":outputs,"events":events,"start_ns":start,"end_ns":now()}))
}

#[tokio::main]
async fn main() -> Result<()> {
    let args: Vec<_> = std::env::args().collect();
    if args.len() != 6 {
        return Err("usage: runtime socket python worker-script config worker-count".into());
    }
    let count = args[5].parse::<usize>()?;
    if count == 0 || count > 8 {
        return Err("worker count must be 1..8".into());
    }
    let worker_socket = format!("{}.workers", args[1]);
    let listener = UnixListener::bind(&args[1])?;
    let worker_listener = UnixListener::bind(&worker_socket)?;
    let mut children: Vec<Child> = Vec::new();
    let mut workers = Vec::new();
    for _ in 0..count {
        let child = Command::new(&args[2])
            .arg(&args[3])
            .arg("--worker")
            .arg(&worker_socket)
            .arg("--config")
            .arg(&args[4])
            .kill_on_drop(true)
            .spawn()?;
        children.push(child);
        let (mut stream, _) =
            tokio::time::timeout(std::time::Duration::from_secs(20), worker_listener.accept())
                .await??;
        if read(&mut stream).await?["ready"] != true {
            return Err("worker handshake failed".into());
        }
        workers.push(Arc::new(Mutex::new(stream)));
    }
    let (mut client, _) = listener.accept().await?;
    write(&mut client, &json!({"ready":true,"clock_ns":now()})).await?;
    loop {
        let request = match read(&mut client).await {
            Ok(v) => v,
            Err(_) => break,
        };
        if request["command"] == "stop" {
            break;
        }
        // Fail closed after a worker/protocol failure: do not reuse a desynchronized pool.
        match tokio::time::timeout(
            std::time::Duration::from_secs(65),
            execute(request, &workers),
        )
        .await
        {
            Ok(Ok(response)) => write(&mut client, &response).await?,
            _ => {
                write(
                    &mut client,
                    &json!({"ok":false,"error":"execution failed or timed out"}),
                )
                .await?;
                break;
            }
        }
    }
    for mut child in children {
        let _ = child.kill().await;
        let _ = child.wait().await;
    }
    let _ = std::fs::remove_file(&args[1]);
    let _ = std::fs::remove_file(&worker_socket);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn refs_require_actual_data() {
        let outputs = BTreeMap::from([("a".into(), json!({"pose":[1,2]}))]);
        assert_eq!(
            resolve(&json!({"$ref":"a.pose.1"}), &outputs).unwrap(),
            json!(2)
        );
        assert!(resolve(&json!({"$ref":"b.pose"}), &outputs).is_err());
    }
    #[test]
    fn actuator_executable_rejected() {
        let n = Node {
            id: "x".into(),
            control_preconditions: vec![],
            input_bindings: json!({}),
            executable: "robot.move".into(),
        };
        assert!(validate(&[n]).is_err());
    }
    #[test]
    fn cycles_rejected() {
        let n = Node {
            id: "x".into(),
            control_preconditions: vec!["x".into()],
            input_bindings: json!({}),
            executable: "noop".into(),
        };
        assert!(validate(&[n]).is_err());
    }
}
