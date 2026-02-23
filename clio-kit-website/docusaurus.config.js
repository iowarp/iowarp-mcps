// @ts-check
// `@type` JSDoc annotations allow editor autocompletion and type checking
// (when paired with `@ts-check`).
// There are various equivalent ways to declare your Docusaurus config.
// See: https://docusaurus.io/docs/api/docusaurus-config

import {themes as prismThemes} from 'prism-react-renderer';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'CLIO Kit - Gnosis Research Center',
  tagline: 'Tools, skills, plugins, and extensions for AI agents. Part of the IoWarp platform. | Developed by Gnosis Research Center (GRC) at Illinois Institute of Technology',
  favicon: 'img/iowarp_logo.png',

  // Future flags, see https://docusaurus.io/docs/api/docusaurus-config#future
  future: {
    v4: true, // Improve compatibility with the upcoming Docusaurus v4
  },

  trailingSlash: false,

  // Set the production url of your site here
  url: 'https://docs.iowarp.ai',
  // Set the /<baseUrl>/ pathname under which your site is served
  baseUrl: '/',

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: 'iowarp', // Usually your GitHub org/user name.
  projectName: 'clio-kit', // Usually your repo name.

  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          sidebarPath: false,
          routeBasePath: 'docs',
          // Please change this to your repo.
          // Remove this to remove the "edit this page" links.
          editUrl:
            'https://github.com/iowarp/clio-kit/tree/main/docs/',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      // Enhanced metadata for social sharing
      metadata: [
        {name: 'description', content: 'CLIO Kit - Tools, skills, plugins, and extensions for AI agents. Part of the IoWarp platform. Features 15+ MCP servers for scientific computing: HDF5, Slurm, Pandas, ArXiv, and more. Built with FastMCP, 150+ tools for HPC workflows. Developed by Gnosis Research Center at Illinois Institute of Technology, supported by NSF.'},
        {name: 'keywords', content: 'CLIO Kit, AI agents, tools, skills, plugins, extensions, MCP, Model Context Protocol, scientific computing, HPC, HDF5, Slurm, Pandas, ADIOS, Parquet, FastMCP, research computing, IoWarp platform, Gnosis Research Center, Illinois Tech, NSF'},
        {property: 'og:title', content: 'CLIO Kit - Tools for AI Agents | IoWarp Platform | Gnosis Research Center'},
        {property: 'og:description', content: 'CLIO Kit: 15+ MCP servers for scientific computing. Part of the IoWarp platform providing tools, skills, plugins, and extensions for AI agents. HDF5, Slurm, Pandas, ArXiv. Built with FastMCP at Illinois Institute of Technology.'},
        {name: 'twitter:card', content: 'summary_large_image'},
        {name: 'twitter:title', content: 'CLIO Kit - Tools for AI Agents | IoWarp Platform'},
        {name: 'twitter:description', content: 'CLIO Kit: MCP servers for scientific computing. Part of the IoWarp platform providing comprehensive agent tooling.'},
      ],
      // Social card for link previews
      image: 'img/iowarp_logo.png',
      navbar: {
        title: 'CLIO Kit',
        logo: {
          alt: 'CLIO Kit Logo',
          src: 'img/iowarp_logo.png',
        },
        items: [
          {
            to: '/',
            position: 'left',
            label: 'Browse MCPs',
          },
          {
            to: '/docs/intro',
            position: 'left',
            label: 'Getting Started',
          },
          {
            href: 'https://pypi.org/project/clio-kit/',
            position: 'right',
            label: 'PyPI',
          },
          {
            href: 'https://grc.iit.edu/',
            position: 'right',
            label: 'GRC',
          },
          {
            href: 'https://github.com/iowarp/clio-kit',
            label: 'GitHub',
            position: 'right',
            className: 'navbar__icon-link navbar__icon-link--github',
          },
        ],
      },
      footer: {
        style: 'dark',
        links: [
          {
            title: 'CLIO Kit',
            items: [
              {
                label: 'Project Overview',
                to: '/docs/intro',
              },
              {
                label: 'Browse Servers',
                to: '/',
              },
              {
                label: 'Platform Website',
                href: 'https://iowarp.ai',
              },
              {
                label: 'GitHub Repository',
                href: 'https://github.com/iowarp/clio-kit',
              },
            ],
          },
          {
            title: 'Research & Funding',
            items: [
              {
                label: 'National Science Foundation',
                href: 'https://new.nsf.gov/',
              },
              {
                label: 'Gnosis Research Center',
                href: 'https://grc.iit.edu/',
              },
              {
                label: 'Illinois Tech',
                href: 'https://www.iit.edu/',
              },
            ],
          },
          {
            title: 'Community',
            items: [
              {
                label: 'GitHub Repository',
                href: 'https://github.com/iowarp/clio-kit',
              },
              {
                label: 'Issue Tracker',
                href: 'https://github.com/iowarp/clio-kit/issues',
              },
              {
                label: 'Zulip Chat',
                href: 'https://iowarp.zulipchat.com/#narrow/channel/543872-Agent-Toolkit',
              },
            ],
          },
          {
            title: 'Distribution',
            items: [
              {
                label: 'PyPI Package',
                href: 'https://pypi.org/project/clio-kit/',
              },
              {
                label: 'Release Notes',
                href: 'https://github.com/iowarp/clio-kit/releases',
              },
            ],
          },
        ],
        copyright: `CLIO Kit · Part of the IoWarp Platform · Developed by Gnosis Research Center (GRC), Illinois Institute of Technology. Funded in part by the National Science Foundation. © ${new Date().getFullYear()}`,
      },
      prism: {
        theme: prismThemes.github,
        darkTheme: prismThemes.dracula,
      },
      colorMode: {
        defaultMode: 'dark',
        disableSwitch: false,
        respectPrefersColorScheme: false,
      },
    }),
};

export default config;
