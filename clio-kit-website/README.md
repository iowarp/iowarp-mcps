# CLIO Kit Documentation Website

This directory contains the Docusaurus-based documentation website for CLIO Kit, the tooling layer of the **[IoWarp Platform](https://iowarp.ai)**.

**v1.0.0** (Beta Public Release - November 11, 2025) focuses on MCP servers for scientific computing. Future releases will expand to include additional skills, plugins, and extensions for AI agents.

**Developed by:** [Gnosis Research Center (GRC)](https://grc.iit.edu/) at [Illinois Institute of Technology](https://www.iit.edu/)  
**Contact:** [grc@illinoistech.edu](mailto:grc@illinoistech.edu)  
**Platform:** [IoWarp.ai](https://iowarp.ai) | **GitHub:** [github.com/iowarp/clio-kit](https://github.com/iowarp/clio-kit)

## 🌐 Live Website

Visit the live website at: **https://docs.iowarp.ai**  
Full platform overview: **[IoWarp.ai](https://iowarp.ai)**

## 📁 Structure

```
docs/
├── docs/                    # Documentation pages
│   ├── intro.md            # Getting started page
│   └── mcps/               # Auto-generated MCP documentation
├── src/                    # React components and assets
│   ├── components/         # Custom React components
│   ├── css/               # Global styles
│   ├── data/              # MCP data for showcase
│   └── pages/             # Custom pages
├── static/                # Static assets
├── docusaurus.config.js   # Docusaurus configuration
└── package.json           # Node.js dependencies
```

## 🔧 Local Development

1. Install dependencies:
   ```bash
   npm install
   ```

2. Start development server:
   ```bash
   npm start
   ```

3. Visit `http://localhost:3000/clio-kit`

## 🚀 Deployment

The website is automatically deployed via GitHub Actions (`docs-and-website.yml`) when changes are pushed to the main branch. The workflow:

1. Generates documentation from MCP source files
2. Builds the Docusaurus site
3. Deploys to GitHub Pages

## 📝 Adding New MCPs

1. Add your MCP to the `mcps/` directory in the repository root
2. Ensure it has proper `pyproject.toml` and `README.md` files
3. The documentation will be automatically generated and deployed

## 🎨 Features

- **Modern React-based UI** with Docusaurus
- **Interactive MCP showcase** with search and filtering
- **Tabbed documentation pages** (Installation, Actions, Examples)
- **Real content extraction** from project files
- **Responsive design** optimized for all devices
- **Dark mode by default** with IoWarp brand colors
- **GitHub integration** for live repository links

## 📊 MCP Categories

- **Data Processing**: Adios, ArXiv, HDF5, Pandas, Parquet, Chronolog
- **Analysis & Visualization**: Plot, Darshan
- **System Management**: Slurm, Lmod, Node Hardware
- **Utilities**: Compression, Parallel Sort, Jarvis

## 🛠️ Technical Details

- **Framework**: Docusaurus 3.x
- **Build Tool**: Node.js + npm
- **Styling**: CSS Modules with custom IoWarp theme
- **Documentation Generation**: Python script (`scripts/generate_docs.py`)
- **Deployment**: GitHub Pages via GitHub Actions