### Sarvam AI Cookbook

Welcome to the **Sarvam AI Cookbook**! This repository provides example code, guides, and tutorials to help you accomplish common tasks using the **Sarvam AI API**. Whether you're building conversational AI, generating text, or working on other AI-powered applications, these resources will help you get started quickly.

#### Getting Started

To use the examples in this cookbook, you'll need a **Sarvam API key**. If you don’t have one yet, sign up for a free account [here](https://dashboard.sarvam.ai/). Once you have your API key, set it as an environment variable:

```bash
export SARVAM_API_KEY=<your API key>
```

Alternatively, you can create a `.env` file in the root of your project with the following content:

```plaintext
SARVAM_API_KEY=<your API key>
```

Most examples are written in **Python**, but the concepts can be adapted to any programming language.

#### Contributing

We welcome examples and fixes! Before opening a pull request:

1. Read [CONTRIBUTING.MD](CONTRIBUTING.MD) for security and API standards.
2. Copy [`examples/TEMPLATE/`](examples/TEMPLATE/) for new notebook recipes.
3. Run local validation: `make check`

CI checks every PR for secret leaks and validates structure for **new** notebook recipes. Current Sarvam models are listed in `scripts/sarvam_api_rules.json` (refreshed weekly from [docs.sarvam.ai](https://docs.sarvam.ai)).

#### Resources

- [Sarvam AI Documentation](https://docs.sarvam.ai)
- [Sarvam AI Playground](https://dashboard.sarvam.ai/)
- [Sarvam AI Discord Group](https://discord.com/invite/8ka56wQaT3)
- [Sarvam AI Github](https://github.com/sarvamai/)
- [Sarvam AI Huggingface](https://huggingface.co/sarvamai)

Explore the cookbook, experiment with the examples, and start building amazing AI-powered applications with Sarvam AI!

**Keep Building 🚀**

