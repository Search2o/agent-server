# Search2o

Search2o is a platform for creating and running AI agents — behind a search interface. A user types a request; search matches it to the right agent and runs it.

This repository contains the Search2o Agent Server: the stateless, asynchronous Python server that runs agents inside your organization.

> **Source available · Proprietary license**
>
> The source code for the Search2o Agent Server is publicly available, but the software is proprietary and is not open source. Use is subject to the [Search2o Software License Agreement](LICENSE.md).
>
> The Agent Server is intended to operate only with Search2o Cloud. Running it requires a valid Search2o license and ongoing authorization from Search2o.

## Getting started

Search2o is in open beta, and anyone interested is welcome.

```
pip install search2o
```

Create your account and get your license key at [Getting started](https://search2o.com/gettingstarted.html), which takes you from install to your first agent.

Full documentation is available at [search2o.com/docs](https://search2o.com/docs/index.html).

## Requirements

* Python 3.12+
* A valid Search2o license with ongoing Search2o authorization
* Access to Search2o Cloud
* Preferably, an LLM API key from one of OpenAI, Anthropic or Google

## License and contributions

Search2o Agent Server is source available and proprietary. Public availability of the source code does not grant permission to modify, redistribute, rebrand, or use the software outside the rights expressly granted by the [Search2o Software License Agreement](LICENSE.md).

External code contributions and pull requests are not currently accepted. Bug reports, feature requests, documentation feedback, and security reports are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).
