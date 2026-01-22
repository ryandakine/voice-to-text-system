# Task Master Setup Guide (Copy-Paste)

This guide allows you to instantly set up Task Master on any new project with your preferred "BlueJeans" configuration (Google Flash + Perplexity).

## 1. Installation & Init
Run these inside your new project folder:

```bash
# 1. Initialize Task Master
task-master init
# (Select "Yes" for storing tasks in Git)

# 2. Create/Update .env file
# Copy the block below into your .env file
```

## 2. API Keys (.env)
Copy this entire block into your `.env` file:

```bash
# AI Model Keys (Standard Set)
ANTHROPIC_API_KEY=your_anthropic_key_here
PERPLEXITY_API_KEY=your_perplexity_key_here
GEMINI_API_KEY=your_gemini_key_here
OPENROUTER_API_KEY=your_openrouter_key_here
```

## 3. Model Configuration
Run these commands to set up the models (Gemini Flash Main, Perplexity Research):

```bash
# Set Main Model: Google Gemini 2.0 Flash (via OpenRouter)
task-master models --set-main google/gemini-2.0-flash-001 --openrouter

# Set Research Model: Perplexity Sonar Reasoning Pro (via OpenRouter)
task-master models --set-research perplexity/sonar-reasoning-pro --openrouter
```

## 4. Work Flow
You are now ready.

1.  Create a PRD in `.taskmaster/docs/prd.txt`
2.  Parse it: `task-master parse-prd .taskmaster/docs/prd.txt`
3.  Expand it: `task-master expand --all --num 10 --research`
4.  Start working: `task-master next`
