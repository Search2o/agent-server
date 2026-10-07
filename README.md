<p align="center">
  <a href="https://search2o.com">
    <img src="https://search2o.com/images/og4.png" alt="Search2o: a platform to build, run, and use AI agents, with a search interface" width="600">
  </a>
</p>

**Website:** [search2o.com](https://search2o.com) · **Source:** [GitHub](https://github.com/Search2o/agent-server) · **Docs:** [search2o.com/docs](https://search2o.com/docs/index.html) . **Skill** [Search2o-skill](https://github.com/Search2o/search2o-skill)

This repository contains the **Search2o Agent Server**: a stateless, asynchronous Python server that runs agents inside your organization, with a REST API and a bundled GUI. Search2o is in open beta.


## Getting started

### 1. Create your account

Create your account at **[Getting started](https://search2o.com/gettingstarted.html)**. Your license key appears on that page when the account is created. No email is sent at this step.

### 2. Install the agent server

Install the agent server with the bundled GUI:

```bash
pip install search2o
```

This GitHub repository holds the agent server without the GUI; the GUI will be published as a separate GitHub project.

### 3. Run the server

macOS / Linux:

```bash
SEARCH2O_LICENSE_KEY=your-license-key search2o
```

Windows PowerShell:

```powershell
$env:SEARCH2O_LICENSE_KEY="your-license-key"
search2o
```

Self-hosted models using Ollama, vLLM or SGLang need no vendor API key. For OpenAI, Anthropic or Gemini, before starting the server, also set one or more of `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` or `GEMINI_API_KEY`. For other LLMs, see [Connecting to other LLMs](https://search2o.com/docs/llm/llm-adapters.html).

### 4. Set up your account

Open `http://127.0.0.1:9020/ui` and click **New user / Forgot password** on the sign-in dialog. Enter the same email you used to create your account in step 1. A code is emailed to that address and no other. Enter the code, choose a password, and sign in.

The server also serves its OpenAPI schema at `/openapi.json`, Swagger UI at `/docs` and ReDoc at `/redoc`.

### 5. Build your first agents

LLMs are called from an agent using an [LLM profile](https://search2o.com/docs/profiles/llm-profiles.html). You can use an existing profile or create a new one.

1. Open **Agents → Drafts** and create a draft. Select your LLM profile, then tell **Draft with AI** what you want.
2. Build two or three task-specific agents. Each agent would typically use one or two of your enterprise systems and handle a specific use case.
3. Validate and publish them. Then add plain-English descriptions so search can find them.
4. Type a question in the search box: the agent matches, runs and answers.

The same agents work in Claude Code through the [search2o-skill](https://github.com/Search2o/search2o-skill).

If you have questions, click the docs icon at the top of the UI, or see the full documentation at [search2o.com/docs](https://search2o.com/docs/index.html). We would love to hear how setting up and running your first few agents went: email [info@search2o.com](mailto:info@search2o.com), or send a message from the message icon in the GUI.

## License

The Search2o Agent Server is source available and proprietary. Use is subject to the [Search2o Software License Agreement](https://search2o.com/legal/license.html).

## Contributions

External code contributions and pull requests are not currently accepted. Bug reports, feature requests, documentation feedback, and security reports are welcome. See [CONTRIBUTING.md](https://github.com/Search2o/agent-server/blob/main/CONTRIBUTING.md).
