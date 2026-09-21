# Third-party notices

- **Graph as Policy**, graph-robots: Apache-2.0. Pinned by `gap-commit.txt`.
  Source: https://github.com/graph-robots/graph-as-policy.
  License: [third_party/graph-as-policy-LICENSE](third_party/graph-as-policy-LICENSE).
- **I2RT**, I2RT Robotics: MIT. Pinned by `i2rt-commit.txt`. Its YAM meshes and
  model are used in the rendered demonstrations; contact-model adaptations are
  documented in the results and source.
  Source: https://github.com/i2rt-robotics/i2rt.
  License: [third_party/i2rt-LICENSE](third_party/i2rt-LICENSE).
- Other Python and Rust dependencies are installed from the committed lockfiles
  and retain their respective licenses. Their source is not vendored in this repo.
- OpenAI Astra and TypeSafe Jev are external hosted services, not included model
  weights. Use requires provider access and is subject to the provider's terms.

Upstream checkouts under `vendor/` are local dependencies fetched by setup, not
part of the Git publication. This independent project is not endorsed by GaP,
I2RT, OpenAI or TypeSafe.
