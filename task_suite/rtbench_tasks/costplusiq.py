"""CostPlusIQ Chat Completions with the shared action/memory and budget contract."""
import json

from .responses import ResponsesPolicy


class CostPlusIQPolicy(ResponsesPolicy):
    provider = "costplusiq"
    endpoint = "https://api.costplusiq.com/v1/chat/completions"

    def _build_payload(self, request):
        source = super()._build_payload(request)
        schema = source["text"]["format"]
        payload = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": source["instructions"] +
                 " Return a JSON object with action (skill, object_id, target_id, orientation) and memory."},
                {"role": "user", "content": source["input"]},
            ],
            "max_tokens": source["max_output_tokens"],
            "stream": False,
            "response_format": {"type": "json_schema", "json_schema": {
                key: schema[key] for key in ("name", "strict", "schema")}},
        }
        if self.config.get("reasoning_effort"):
            payload["reasoning_effort"] = self.config["reasoning_effort"]
        if "enable_thinking" in self.config:
            payload["chat_template_kwargs"] = {"enable_thinking": self.config["enable_thinking"]}
        return payload

    def _parse_result(self, result):
        if result.get("model") not in self.config.get("accepted_response_models", [self.model_id]):
            raise ValueError("unexpected response model")
        choices = result.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or choices[0].get("finish_reason") != "stop":
            raise ValueError("incomplete or ambiguous chat completion")
        message = choices[0].get("message", {})
        if message.get("refusal") or message.get("tool_calls"):
            raise ValueError("refusal or unexpected tool calls")
        if message.get("role") != "assistant" or not isinstance(message.get("content"), str):
            raise ValueError("missing assistant content")
        usage = result.get("usage", {})
        return json.loads(message["content"]), {
            "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"),
        }
