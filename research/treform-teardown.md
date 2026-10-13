# How Treform.ai is built, and a plan for a Revit-only version

*Research date: 13 October 2026*

## Where this information came from

- Treform's public web pages: the home page, pricing, manifesto, download page and subprocessor list.
- The public code that the web app (app.treform.ai) sends to any browser.
- The public Windows installer (`Treform-windows-x64-setup.exe`, v1.0.64), unpacked to see which files it puts on a computer.

Nothing here required a login. Treform's server-side code isn't public, so the parts about their servers are inferred from how the app talks to them.

**Use this to learn the approach, not to copy their code.** Their files are copyrighted. The ideas below are common practice, and open-source examples of each exist (see the last section).

---

## 1. What Treform is (in plain words)

Treform is an AI assistant for architects. You type what you want ("a 25-storey tower with an angled top"), and it builds the 3D model for you. It can do this in two places:

1. **Its own web editor** at app.treform.ai, a 3D modeler that runs in the browser.
2. **Inside your existing design software.** A small floating window, "Treform Desktop", sits next to Rhino, Revit, SketchUp or Blender and controls that program for you.

Founder: **Zilin Jing** (named in the manifesto; contact zilin@treform.ai). It is a very small team.

Product history from the in-app "What's new" notes:
- Jul 2026: "Image to model, massively improved"
- Sep 2026: "Treform 2.0", which added Revit, Blender and SketchUp alongside Rhino and Grasshopper

---

## 2. The big picture: three pieces

```
 ┌────────────────────────┐      ┌───────────────────────────┐      ┌──────────────────────┐
 │  Treform cloud         │      │  Treform Desktop          │      │  Revit (or Rhino…)   │
 │  (website + AI brain)  │◄────►│  small floating window    │◄────►│  + Treform add-in    │
 │  Vercel + Supabase     │ net  │  on your computer (Tauri) │local │  runs Python inside  │
 │  calls Claude / GPT    │      │  shows the chat           │ only │  Revit               │
 └────────────────────────┘      └───────────────────────────┘      └──────────────────────┘
```

1. **The cloud (the "brain")** holds the AI instructions, calls the AI models, and stores accounts, projects and billing.
2. **The desktop app (the "messenger")** is a small window that shows the chat. It passes messages between the cloud and the design program on your computer.
3. **The add-in (the "hands")** is a small plugin installed into Revit. It receives a piece of code, runs it inside Revit, and reports back what happened.

---

## 3. Each piece in detail

### 3a. The cloud / website

| What | What they use | Evidence |
|---|---|---|
| Website & app framework | **Next.js** (React), built with Turbopack | page headers and code files |
| Hosting | **Vercel** | `server: Vercel` header; subprocessor list |
| Login, database, file storage | **Supabase** (Postgres) + **Google sign-in** | subprocessor list; Supabase address in the code |
| Payments | **Whop** (Stripe underneath) | subprocessor list; `/api/whop/checkout` |
| Email | **Brevo** | subprocessor list |
| AI models | **Anthropic Claude** (Haiku 4.5, Sonnet 5, Opus 5, Fable 5.1) and **OpenAI** (gpt-5.6-sol, gpt-5.6-terra, gpt-6-astra) | model names in the app code |
| Image renders | **FAL** running Google's "nano-banana-2" image editor | subprocessor list |
| Styling | Tailwind CSS | class names in the code |

Interesting detail: on the "bring your own key" screen they recommend an **OpenAI key** ("Best results: an OpenAI key with gpt-5.6-sol access"). For a Claude key they warn: "Expect lower build quality than with an OpenAI key." So they test both and pick whichever builds geometry best.

**The web 3D editor** uses:
- **Three.js** to draw 3D in the browser
- **Manifold**, a geometry library for cutting and combining solid shapes
- **rhino3dm** to open Rhino files
- A map library for the site and terrain import (OpenStreetMap data)

### 3b. The AI "brain": how a request is processed

The app talks to many server endpoints, such as `/api/rhino-agent/turn`, `/dispatch`, `/exec-tool`, `/critique`, `/scene-context`, `/snapshot` and `/settle-turn`. From how they are called, a single request works like this:

1. You type a request. The desktop app sends it to the cloud, along with your selection, the active program (Revit, etc.), a scene snapshot and any reference images.
2. The cloud asks the AI model what to do. The AI answers with a **tool call**, which usually means "run this piece of code in Revit".
3. The cloud sends that code back to your desktop app, which passes it to Revit. Revit runs it, and the result goes back to the cloud.
4. This repeats until the job is done, up to **12 rounds** on normal plans and **30** for bring-your-own-key users. There is a hard safety limit of 64 local steps.
5. Usage is then counted ("settle"). If something failed, the edit is refunded ("refund-turn").

**AI instructions.** The instructions given to the AI are long, detailed documents. They begin "You are Treform, an AI architectural design assistant…" and have different modes: **Chat** (questions only), **Build** (precise walls, slabs, doors and windows, code compliance) and **Formmaking** (sculptural shapes). The instructions stress:
- "The user's brief is primary": if they say "twin towers", there must be two towers.
- Check the site boundary before building anything.
- For reference images, use a three-step flow: analyse the image, solve the layout, then build.
- A built-in library of famous buildings ("precedents") that the AI recalls for briefs like "something like Zaha Hadid".
- Self-critique: score the result and redo the weakest part.

**Automatic error tips.** This is a clever, cheap trick that matters a lot for Revit. When Revit code fails with a known error, the app appends a plain-English hint before the AI tries again. Real examples from their Revit list:
- `'ElementId' has no attribute 'IntegerValue'` → "ElementId has no IntegerValue since Revit 2024. Use element_id.Value."
- "Cannot change the active view of a modifiable document" → "Put the view change in its own script that contains the marker `# TF_NO_TXN`."
- "is not JSON serializable" → "Convert Revit values before printing JSON: str(element_id), float(number)…"
- "may not be used as a DirectShape category" → "Use ElementId(BuiltInCategory.OST_GenericModel)…"
- "name cannot include prohibited characters" → "Revit names cannot contain { } [ ] | ; < > ? ` ~ or :"

The app also quietly rewrites `.IntegerValue` to `.Value` in AI-written Revit code before it runs.

**Revit-specific AI tools.** These are what the AI can call: `rv_get_document_info`, `rv_get_selection`, `run_python` (run any Revit code) and `get_viewport_image` (take a screenshot of the Revit view, so the AI can see its own work).

### 3c. The desktop app

- Built with **Tauri**, a lightweight way to wrap a website in a desktop window, with a small **Rust** core. That keeps the Windows installer small: 23 MB in total, mostly plugins.
- The window simply shows app.treform.ai inside it, so updating the website updates the desktop app too.
- The Rust core adds what a website can't do on its own:
  - **Detect** which design programs are installed (`detect_apps`).
  - **Install or uninstall** the add-in for each program (`install_host_bridge`).
  - **Launch** the program (`launch_host_app`).
  - **Pass messages** to the add-in (`host_bridge_proxy`).
  - **Dock** the floating panel to the side of the screen.
- Sign-in works by opening the browser and returning through a `treform://` link.

### 3d. The Revit add-in (the most relevant part for you)

These files were found in the installer under `resources/bridge/revit/`:

| File | What it is |
|---|---|
| `Treform.addin` | The small XML file Revit reads at start-up to load the plugin. It is copied to `%AppData%\Autodesk\Revit\Addins\<year>\`. |
| `net48/TreformRevitBridge.dll` | The add-in for **Revit 2021–2024**, which use .NET Framework 4.8. |
| `net8.0-windows/TreformRevitBridge.dll` | The add-in for **Revit 2025–2026**, which use .NET 8. |
| `IronPython.dll` + `lib/` | **IronPython**, a Python engine bundled inside the add-in, so the AI can write Python that talks to the Revit API. No pyRevit or separate Python install is needed. |

The add-in is tiny, about 34 KB of their own code (version 0.1.0). From the text inside it, this is what it does:

1. When Revit starts, it **opens a small local web server** on `http://127.0.0.1:<port>`, using a port from **12500–12549**. It is only reachable from your own computer.
2. It **writes a small "I'm here" file** (`{pid}-{port}.json` in a `Treform/revit-bridge/listeners` folder), so the desktop app can find which port Revit is on. This also handles two copies of Revit running at once.
3. It speaks **MCP (Model Context Protocol)**, the standard way to let AI models use tools (protocol version `2024-11-05`, JSON-RPC). It offers just **two tools**:
   - **`run_python`** takes a script and runs it inside Revit with `doc`, `uidoc` and `__revit__` ready to use, then returns the printed output or the error.
   - **`get_viewport_image`** exports the current view as a PNG, so the AI can see the result.
4. It **wraps every script in a Revit "Transaction"** automatically, so changes are saved and can be undone with Ctrl+Z. A script can opt out with `# TF_NO_TXN`, which is needed for things like switching views.
5. It uses Revit's **ExternalEvent** mechanism. This is the official, safe way to run outside requests on Revit's main thread, because Revit crashes if you touch the model from another thread.
6. It gives friendly errors when Revit is busy, for example "is a modal dialog open?" or "close any open dialog or edit mode and try again".

**Key insight:** Treform does **not** build hundreds of hand-made Revit commands. It gives the AI one powerful tool ("run Python in Revit") plus a screenshot tool. The quality comes from three things: very good AI instructions, an error-tip list, and letting the AI see and retry.

### 3e. How other programs are connected (same pattern)

| Program | Scripting language the AI writes | Local port range |
|---|---|---|
| Rhino / Grasshopper | Python (uses McNeel's own "Rhino MCP Platform" plugin) | 10500+ |
| SketchUp | Ruby | 11500+ |
| **Revit** | **Python (IronPython)** | **12500+** |
| Blender | Python | 13500+ |
| FreeCAD, Fusion 360, Cinema 4D, SolidWorks, Vectorworks | Python | 15500–21500+ (most not yet switched on) |
| AutoCAD | AutoLISP | 19500+ (planned) |
| Archicad | JSON commands | 19723+ (hidden) |

---

## 4. Business model

| Plan | Price | Includes |
|---|---|---|
| Free | $0 | 3 AI edits/month, Haiku only, no exports |
| Pro | $39/mo (yearly) | 30 edits, 25 renders |
| Studio | $99/mo (yearly) | 80 edits, 100 renders, top models |
| BYOK | $25/mo | Unlimited edits on your own Claude/OpenAI key |
| Team | $40/seat/mo, 10-seat minimum | Shared company key |
| Student | $25/mo or $69 per 3 months | Pro features |

Extra edits cost $0.20 each. **"Bring your own key"** is a smart move for a small team: heavy users pay the AI company directly, so Treform doesn't carry the AI cost.

---

## 5. Blueprint for a Revit-only version

Because you only target Revit, you can **skip the desktop app entirely**. Revit add-ins can show their own panel inside Revit, which is simpler and feels more native than a floating window.

### Simplest version (a good first product)

```
 ┌──────────────────────────── Revit ─────────────────────────────┐
 │  Your add-in (C#)                                              │
 │   ├─ Dockable chat panel (WebView2 showing your web page)      │
 │   ├─ ExternalEvent → runs code safely on Revit's main thread   │
 │   ├─ Script runner (IronPython, or C# compiled on the fly)     │
 │   └─ Auto Transaction + undo, screenshot tool                  │
 └───────────────▲────────────────────────────────────────────────┘
                 │ internet
 ┌───────────────┴────────────────┐
 │  Your server (Next.js on Vercel)│  ← holds AI instructions & API keys
 │  Supabase for accounts/usage    │  ← Claude / OpenAI APIs
 │  Stripe for payments            │
 └─────────────────────────────────┘
```

### Ingredients and who builds them

| Piece | Skills needed | Rough effort for one experienced developer |
|---|---|---|
| Revit add-in with a chat panel, ExternalEvent and script runner | C# / .NET, Revit API | 3–6 weeks |
| Support for Revit 2024–2027 (two .NET builds) | C#, packaging | 1–2 weeks |
| AI loop with tool calling and retries | TypeScript or Python, Claude/OpenAI APIs | 2–4 weeks |
| AI instructions + error-tip list (the "secret sauce") | Revit expertise + lots of testing | Ongoing, and the most important part |
| Accounts, usage limits, billing | Supabase + Stripe | 1–2 weeks |
| Installer (.msi or .exe) that puts files in the Addins folder | Windows packaging | 1 week |
| Code-signing certificate | Purchase | Cost only (approx. a few hundred $ a year) |

**A realistic first version is about 2–3 months for one strong developer.** Making it reliable is mostly the ongoing work of testing prompts and adding to the error-tip list.

### Where a Revit-only product can beat Treform

Treform is spread across 10+ programs, and its Revit support is still "beta". A focused product can go deeper on what Revit users actually pay for:
- **Documentation work**: sheets, views, tags, dimensions, schedules and renumbering, which are tedious and repetitive.
- **Model checking**: naming standards, missing parameters, clashes, code checks.
- **Families and types**: create and modify families and types correctly, not just "DirectShape" blobs. Treform's error list shows it often creates generic DirectShape geometry.
- **Firm standards**: learning a company's templates and naming rules.

### Important decisions and risks

1. **Safety.** Letting AI run any code inside someone's Revit model is powerful but risky. Always use Transactions so changes can be undone, show a preview or confirmation for big changes, and consider blocking file deletion, saving over files and similar actions.
2. **Python or C#?** IronPython (Treform's choice) is easy for AI to write but uses old Python 2.7-style syntax. The alternative is having the AI write C#, compiled on the fly. Both work; AI models are very good at C# Revit code.
3. **Revit version differences.** Each yearly Revit release changes the API a little (for example, `ElementId.IntegerValue` was removed). Build your error-tip list from day one.
4. **Competition.** Autodesk itself launched **Autodesk Assistant in Revit** (tech preview, April 2026). **ArchiLabs** (Y Combinator) and **BIMlogiq Copilot** also exist. You need a clear niche.
5. **Autodesk rules.** To list in the Autodesk App Store you need a "Vendor ID" (Treform uses `TREF`) and must pass their review.

---

## 6. Open-source starting points

These are free projects that already do parts of this. **Check each licence before reusing code.**

- **mcp-servers-for-revit**: Revit add-in + MCP server; supports Revit 2020–2026.
- **Sam-AEC/Autodesk-Revit-MCP-Server**: C# add-in using ExternalEvent, plus a Python MCP server.
- **Demolinator/revit-mcp-server**: works through pyRevit, supports Revit 2024–2027.
- **oakplank/RevitMCP**: pyRevit extension with a chat web page; supports Claude, OpenAI and Google.
- **pyRevit**: the most popular free Python tool platform for Revit; a good way to prototype quickly.

A fast prototype path, before building anything custom: install pyRevit plus one of the MCP servers above, connect it to Claude Desktop, and try real tasks. That shows what works in a few days, for free.

---

## Sources

- https://treform.ai, /pricing, /manifesto, /download, /subprocessors
- https://app.treform.ai (public JavaScript bundle)
- Treform Windows installer v1.0.64 (public download)
- https://www.autodesk.com/blogs/aec/2026/04/22/autodesk-assistant-in-revit-tech-preview/
- https://www.ycombinator.com/companies/archilabs
- https://glama.ai/mcp/servers/Demolinator/revit-mcp-server
- https://playbooks.com/mcp/oakplank-revit
- https://www.sourcepulse.org/projects/33683136
- https://claudemarketplaces.com/mcp/sam-aec/autodesk-revit-mcp-server
