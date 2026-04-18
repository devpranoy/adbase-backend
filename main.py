import os

from flask import Flask
from flask_cors import CORS

from endpoints import api_bp

app = Flask(__name__)

# CORS: allow frontend origin(s). Comma-separated list in env, or default (dev + production)
_default_origins = (
    "http://127.0.0.1:5500,http://localhost:5500,http://localhost:3000,http://127.0.0.1:3000,"
    "https://tryadbase.com,https://www.tryadbase.com"
)
_cors_origins = os.environ.get("CORS_ORIGINS", _default_origins)
CORS(app, origins=[o.strip() for o in _cors_origins.split(",") if o.strip()], supports_credentials=True)

app.register_blueprint(api_bp)


@app.get("/")
def read_root():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Vercel + Flask</title>
        <link rel="icon" type="image/svg+xml" href="/favicon.ico">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
                background-color: #000000; color: #ffffff; line-height: 1.6; min-height: 100vh;
                display: flex; flex-direction: column;
            }
            header { border-bottom: 1px solid #333333; padding: 0; }
            nav { max-width: 1200px; margin: 0 auto; display: flex; align-items: center; padding: 1rem 2rem; gap: 2rem; }
            .logo { font-size: 1.25rem; font-weight: 600; color: #ffffff; text-decoration: none; }
            .nav-links { display: flex; gap: 1.5rem; margin-left: auto; }
            .nav-links a { text-decoration: none; color: #888888; padding: 0.5rem 1rem; border-radius: 6px; transition: all 0.2s ease; font-size: 0.875rem; font-weight: 500; }
            .nav-links a:hover { color: #ffffff; background-color: #111111; }
            main { flex: 1; max-width: 1200px; margin: 0 auto; padding: 4rem 2rem; display: flex; flex-direction: column; align-items: center; text-align: center; }
            .hero { margin-bottom: 3rem; }
            .hero-code { margin-top: 2rem; width: 100%; max-width: 900px; display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }
            .hero-code pre { background-color: #0a0a0a; border: 1px solid #333333; border-radius: 8px; padding: 1.5rem; text-align: left; grid-column: 1 / -1; }
            h1 { font-size: 3rem; font-weight: 700; margin-bottom: 1rem; background: linear-gradient(to right, #ffffff, #888888); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
            .subtitle { font-size: 1.25rem; color: #888888; margin-bottom: 2rem; max-width: 600px; }
            .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; width: 100%; max-width: 900px; }
            .card { background-color: #111111; border: 1px solid #333333; border-radius: 8px; padding: 1.5rem; transition: all 0.2s ease; text-align: left; }
            .card:hover { border-color: #555555; transform: translateY(-2px); }
            .card h3 { font-size: 1.125rem; font-weight: 600; margin-bottom: 0.5rem; color: #ffffff; }
            .card p { color: #888888; font-size: 0.875rem; margin-bottom: 1rem; }
            .card a { display: inline-flex; align-items: center; color: #ffffff; text-decoration: none; font-size: 0.875rem; font-weight: 500; padding: 0.5rem 1rem; background-color: #222222; border-radius: 6px; border: 1px solid #333333; transition: all 0.2s ease; }
            .card a:hover { background-color: #333333; border-color: #555555; }
            .status-badge { display: inline-flex; align-items: center; gap: 0.5rem; background-color: #0070f3; color: #ffffff; padding: 0.25rem 0.75rem; border-radius: 20px; font-size: 0.75rem; font-weight: 500; margin-bottom: 2rem; }
            .status-dot { width: 6px; height: 6px; background-color: #00ff88; border-radius: 50%; }
            pre { background-color: #0a0a0a; border: 1px solid #333333; border-radius: 6px; padding: 1rem; overflow-x: auto; margin: 0; }
            code { font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace; font-size: 0.85rem; line-height: 1.5; color: #ffffff; }
            .keyword { color: #ff79c6; }
            .string { color: #f1fa8c; }
            .function { color: #50fa7b; }
            .class { color: #8be9fd; }
            .module { color: #8be9fd; }
            .variable { color: #f8f8f2; }
            .decorator { color: #ffb86c; }
            @media (max-width: 768px) {
                nav { padding: 1rem; flex-direction: column; gap: 1rem; }
                .nav-links { margin-left: 0; }
                main { padding: 2rem 1rem; }
                h1 { font-size: 2rem; }
                .hero-code { grid-template-columns: 1fr; }
                .cards { grid-template-columns: 1fr; }
            }
        </style>
    </head>
    <body>
        <header>
            <nav>
                <a href="/" class="logo">Vercel + Flask</a>
                <div class="nav-links">
                    <a href="/docs">Docs</a>
                    <a href="/openapi.json">OpenAPI</a>
                </div>
            </nav>
        </header>
        <main>
            <div class="hero">
                <h1>Vercel + Flask</h1>
                <div class="hero-code">
                    <pre><code><span class="keyword">from</span> <span class="module">flask</span> <span class="keyword">import</span> <span class="class">Flask</span>

<span class="variable">app</span> = <span class="class">Flask</span>(<span class="string">__name__</span>)

<span class="decorator">@app.get</span>(<span class="string">"/"</span>)
<span class="keyword">def</span> <span class="function">read_root</span>():
    <span class="keyword">return</span> {<span class="string">"Python"</span>: <span class="string">"on Vercel"</span>}</code></pre>
                </div>
            </div>

                <div class="cards">
                    <div class="card">
                        <h3>Swagger Docs</h3>
                        <p>Browse every endpoint, inspect request payloads, and try the API directly from the browser.</p>
                        <a href="/docs">Open Docs →</a>
                    </div>
                    <div class="card">
                        <h3>OpenAPI JSON</h3>
                        <p>Share the machine-readable API contract with frontend, QA, or external integrators.</p>
                        <a href="/openapi.json">View Spec →</a>
                    </div>
                </div>
        </main>
    </body>
    </html>
    """
