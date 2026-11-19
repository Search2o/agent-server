<p align="center">
  <a href="https://tactet.com">
    <img src="https://tactet.com/images/og13.png" alt="Tactet: Model‑neutral agent platform for the enterprise" width="600">
  </a>
</p>

**Website:** [tactet.com](https://tactet.com) · **Source:** [GitHub](https://github.com/tactet-ai/agent-server) · **GUI source:** [GitHub](https://github.com/tactet-ai/ui) · **Docs:** [tactet.com/docs](https://tactet.com/docs/index.html) . **Skill** [Tactet-skill](https://github.com/tactet-ai/tactet-skill)

This repository contains the **Tactet Agent Server**: a stateless, asynchronous Python server, that is part of the Tactet agent platform. It runs agents inside your organization and maintains state using the cloud service. It includes a REST API and a bundled GUI. Tactet is in open beta.


## Getting started

### 1. Create your account

Create your account at **[Getting started](https://tactet.com/gettingstarted.html)**. Your license key appears on that page when the account is created. No email is sent at this step.

### 2. Install the agent server

Install the agent server with the bundled GUI:

```bash
pip install tactet
```

To install from the source instead, clone the agent server and install it from the clone. The clone does not include the GUI:

```bash
git clone https://github.com/tactet-ai/agent-server.git
pip install -e agent-server
```

To install the GUI from the source, follow the instructions in the README of the [GUI repository](https://github.com/tactet-ai/ui).

### 3. Run the server

macOS / Linux:

```bash
TACTET_LICENSE_KEY=your-license-key tactet
```

Windows PowerShell:

```powershell
$env:TACTET_LICENSE_KEY="your-license-key"
tactet
```

Self-hosted models using Ollama, vLLM or SGLang need no vendor API key. For OpenAI, Anthropic or Gemini, before starting the server, also set one or more of `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` or `GEMINI_API_KEY`. For other LLMs, see [Connecting to other LLMs](https://tactet.com/docs/llm/llm-adapters.html).

### 4. Set up your account

Open `http://127.0.0.1:9020/ui` and click **New user / Forgot password** on the sign-in dialog. Enter the same email you used to create your account in step 1. A code is emailed to that address and no other. Enter the code, choose a password, and sign in.

The server also serves its OpenAPI schema at `/openapi.json`, Swagger UI at `/docs` and ReDoc at `/redoc`.

### 5. Build your first agents

LLMs are called from an agent using an [LLM profile](https://tactet.com/docs/profiles/llm-profiles.html). You can use an existing profile or create a new one.

1. Open **Agents → Drafts** and create a draft. Select your LLM profile, then tell **Draft with AI** what you want.
2. Build two or three task-specific agents. Each agent would typically use one or two of your enterprise systems and handle a specific use case.
3. Validate and publish them. Then add plain-English descriptions so search can find them.
4. Type a question in the search box: the agent matches, runs and answers.

The same agents work in Claude Code through the [tactet-skill](https://github.com/tactet-ai/tactet-skill).

If you have questions, click the docs icon at the top of the UI, or see the full documentation at [tactet.com/docs](https://tactet.com/docs/index.html). We would love to hear how setting up and running your first few agents went: email [info@tactet.com](mailto:info@tactet.com), or send a message from the message icon in the GUI.

## License

The Tactet Agent Server is source available and proprietary. Use is subject to the [Tactet Software License Agreement](https://tactet.com/legal/license.html).

## Contributions

External code contributions and pull requests are not currently accepted. Bug reports, feature requests, documentation feedback, and security reports are welcome. See [CONTRIBUTING.md](https://github.com/tactet-ai/agent-server/blob/main/CONTRIBUTING.md).
