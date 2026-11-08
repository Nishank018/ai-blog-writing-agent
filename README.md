
# Draftwell Studio ✍️

Draftwell Studio is a personal AI-powered blog writing workspace I'm building with Python, LangGraph, and React.

The idea is to use multiple AI agents to handle different stages of writing a blog, from research and planning to writing and organizing the final article.

I'm building this project to learn more about AI agents, LLMs, backend development, and how different technologies work together.

## Features

- AI-powered blog generation
- Topic routing and optional web research
- Automatic blog planning and section generation
- Parallel AI writing agents using LangGraph
- Citation checking
- Image search and attribution
- Markdown blog saving
- React-based dashboard

## Architecture

The workflow uses LangGraph to coordinate different agents:

```text
                  Blog Topic
                      |
                    Router
                      |
              Research (optional)
                      |
                    Planner
                      |
               Section Workers
               (Parallel Writing)
                      |
                    Reducer
                      |
                 Blog Editor
                      |
                Image Pipeline
                      |
                  Blog Saver
                      |
                Markdown Blog
```

### Agent Responsibilities

| Component | Responsibility |
|---|---|
| Router | Decides whether research is needed. |
| Researcher | Collects relevant information. |
| Planner | Creates the blog outline. |
| Section Workers | Write individual sections in parallel. |
| Reducer | Combines the generated sections. |
| Blog Editor | Checks citations against research sources. |
| Image Pipeline | Finds images and adds attributions. |
| Blog Saver | Saves the final article as Markdown. |

## Tech Stack

- **Frontend:** React, TypeScript, Vite
- **Backend:** Python, FastAPI
- **AI & Agents:** LangChain, LangGraph, Google Gemini
- **Research:** Tavily
- **Images:** Wikimedia Commons

## What I'm Learning

While building Draftwell Studio, I'm exploring:

- Multi-agent workflows with LangGraph
- Structured outputs and Pydantic
- Parallel execution of AI agents
- Connecting React with a Python backend
- API integration and streaming responses
- Working with Markdown and image attribution

## Getting Started

### Prerequisites

- Python 3.11 or newer
- Node.js and npm
- Google Gemini API key
- Tavily API key for research functionality

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
```

### 2. Set up the Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the project's Python dependencies using its dependency file.

### 3. Configure environment variables

Create a `.env` file in the root directory:

```env
GEMINI_API_KEY=your_gemini_api_key
TAVILY_API_KEY=your_tavily_api_key
```

Never commit your `.env` file or expose your API keys.

### 4. Start the backend

```bash
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

### 5. Start the frontend

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL provided by Vite.

## Project Status

Draftwell Studio is an ongoing open-source learning project.

I'm building, testing, fixing bugs, and documenting what I learn along the way. More improvements are coming!

## Contributing

Suggestions, bug reports, and improvements are welcome. Feel free to open an issue or submit a pull request.

