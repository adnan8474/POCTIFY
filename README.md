# POCTIFY Interactive

This repository contains a simple Streamlit tool and a static landing page for **POCTIFY Interactive Tools**.

## Landing Page
The `landing-page` folder holds a React + Tailwind CSS landing page. Open `landing-page/index.html` in any web server or browser to view the site.

### Updating Tools
The list of tools shown on the landing page is defined in `landing-page/app.js` inside the `tools` array within the `ToolsSection` component. Each entry accepts:

- `icon` – emoji or icon text
- `title` – tool name
- `description` – short description
- `status` – `"Live"`, `"Coming Soon"`, or `"Beta"`
- `url` – link for the button

Add or modify objects in this array to update the displayed tools.

## Streamlit App
The barcode sharing detector lives in `app.py` and can be run with:

```bash
pip install -r requirements.txt
streamlit run app.py
```
