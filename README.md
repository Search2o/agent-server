# Search2o

Search2o is a platform for creating and running AI agents behind a search interface.

**Website:** [search2o.com](https://search2o.com) · **Source:** [GitHub](https://github.com/Search2o/agent-server)

This repository contains the Search2o Agent Server: a stateless, asynchronous Python server that runs agents inside your organization, with a REST API and a bundled GUI.

## Getting started

Search2o is in open beta.

Install the Agent Server:

```bash
pip install search2o
```

Running this server requires a license key, which you can get at [Getting started](https://search2o.com/gettingstarted.html).

Start the server with your license key and an LLM API key from one of OpenAI, Anthropic, or Google:

**OpenAI**

```bash
SEARCH2O_LICENSE_KEY=your-license-key OPENAI_API_KEY=your-api-key search2o
```

**Anthropic**

```bash
SEARCH2O_LICENSE_KEY=your-license-key ANTHROPIC_API_KEY=your-api-key search2o
```

**Google**

```bash
SEARCH2O_LICENSE_KEY=your-license-key GEMINI_API_KEY=your-api-key search2o
```

## Open the GUI

Open `http://127.0.0.1:9020/ui` and click **New user / Forgot password** on the sign-in dialog. Enter the email associated with your Search2o account; an email with a code arrives. Enter the code, choose a password, and sign in.

The same server serves its OpenAPI schema at `/openapi.json`, Swagger UI at `/docs`, and ReDoc at `/redoc`.

## Create two or three agents

Open **Agents → Drafts** and create a draft. Tick your LLM profile, then tell **Draft with AI** what you want. Make two or three, so that search has a choice:

* *Write a simple agent that forwards the user's query to the LLM.*
* *A tool-calling agent that fetches a customer's orders from our orders API.*
* *An agent that asks for a city, then answers questions about it.*

Validate and publish them. Then add a plain-English description to each agent and wait for the indexing to finish.

## Search

Type a question in the search box: the agent matches, runs, and answers.

You are all set. Explore, and build the agents your team needs. If you have questions, click the docs icon in the GUI. If you need support, click the help icon.

## Bring your team

When you’re ready for your team, request an Evaluation license from the Account page in the GUI. You are notified of the approval by email within one business day.

Then start the server in a common place — nothing else has to change.

See [Pricing](https://search2o.com/pricing.html) for what each level includes.

Full documentation is available at [search2o.com/docs](https://search2o.com/docs/index.html).

## License

The Search2o Agent Server is source available and proprietary. Use is subject to the [Search2o Software License Agreement](LICENSE.md).

The Agent Server is intended to operate only with Search2o Cloud. Running it requires a valid Search2o license and ongoing authorization from Search2o.

## Contributions

External code contributions and pull requests are not currently accepted. Bug reports, feature requests, documentation feedback, and security reports are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).
