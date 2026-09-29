<p align="center">
  <a href="https://search2o.com">
    <img src="https://search2o.com/images/og2.png" alt="Search2o: a platform to build, run, and use AI agents, with a search interface" width="600">
  </a>
</p>

**Website:** [search2o.com](https://search2o.com) · **Source:** [GitHub](https://github.com/Search2o/agent-server) · **Docs:** [search2o.com/docs](https://search2o.com/docs/index.html) . **Skill** [Search2o-skill](https://github.com/Search2o/search2o-skill)

This repository contains the **Search2o Agent Server**: a stateless, asynchronous Python server that runs agents inside your organization, with a REST API and a bundled GUI. Search2o is in open beta.


## Getting started

### 1. Install

```bash
pip install search2o
```

The `pip` package includes the GUI. Cloning the GitHub repository does not include it.

### 2. Get a license key

Running this server requires a license key. Get one at **[Getting started](https://search2o.com/gettingstarted.html)**.

### 3. Start the server

Start the server with your license key and an API key from OpenAI, Anthropic, or Google:

| Vendor | Command |
|---|---|
| **OpenAI** | `SEARCH2O_LICENSE_KEY=your-license-key OPENAI_API_KEY=your-api-key search2o` |
| **Anthropic** | `SEARCH2O_LICENSE_KEY=your-license-key ANTHROPIC_API_KEY=your-api-key search2o` |
| **Google** | `SEARCH2O_LICENSE_KEY=your-license-key GEMINI_API_KEY=your-api-key search2o` |

If you use other LLMs, see [Connecting to other LLMs](https://search2o.com/docs/llm/llm-adapters.html).

### 4. Open the GUI

1. Open `http://127.0.0.1:9020/ui`.
2. Click **New user / Forgot password** on the sign-in dialog.
3. Enter the email you used to create your account at **[Getting started](https://search2o.com/gettingstarted.html)**. You will receive an email with a code.
4. Enter the code, choose a password, and sign in.

The same server serves its OpenAPI schema at `/openapi.json`, Swagger UI at `/docs`, and ReDoc at `/redoc`.

You can build, index, and test agents locally. The Agent Server is stateless, so you can later run it in a shared environment without moving your agents or configuration.

Full documentation is available at [search2o.com/docs](https://search2o.com/docs/index.html).

## License

The Search2o Agent Server is source available and proprietary. Use is subject to the [Search2o Software License Agreement](https://search2o.com/legal/license.html).

## Contributions

External code contributions and pull requests are not currently accepted. Bug reports, feature requests, documentation feedback, and security reports are welcome. See [CONTRIBUTING.md](https://github.com/Search2o/agent-server/blob/main/CONTRIBUTING.md).
