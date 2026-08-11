---
name: surveying-research-literature
description: Builds a literature survey from ArXiv and locates the datasets behind it on the National Data Platform, ending in a citable bibliography and staged local files. Use when the user asks what has been published on a topic, wants papers on a subject or by an author, asks for a BibTeX bibliography, or wants the data underlying a paper rather than only the paper.
category: Research
servers: clio-arxiv, clio-ndp
tools: clio-arxiv:search_arxiv, clio-arxiv:search_by_abstract, clio-arxiv:search_papers_by_author, clio-arxiv:search_date_range, clio-arxiv:get_paper_details, clio-arxiv:find_similar_papers, clio-arxiv:export_to_bibtex, clio-arxiv:download_paper_pdf, clio-ndp:search_datasets, clio-ndp:get_dataset_details, clio-ndp:stage_resource, clio-arxiv:get_pdf_url
---

# Surveying research literature

A survey that stops at titles is not a survey. The value is in narrowing
deliberately, then following the good results into their data.

## Workflow

```
- [ ] 1. Search broadly, then narrow
- [ ] 2. Read details for the shortlist only
- [ ] 3. Expand from the best result, not the query
- [ ] 4. Export the bibliography
- [ ] 5. Follow the work to its data
```

## 1. Search, then narrow

Start with `clio-arxiv:search_arxiv` on the topic. Then narrow using whichever
axis the question actually implies:

| The user is asking about | Use |
|---|---|
| a topic or concept | `clio-arxiv:search_by_abstract` — matches content, not just titles |
| a person's work | `clio-arxiv:search_papers_by_author` |
| recent developments | `clio-arxiv:search_date_range` |

Prefer abstract search over title search for concepts. Titles are marketing;
abstracts contain the method.

## 2. Read details for the shortlist only

`clio-arxiv:get_paper_details` per paper, on the handful worth keeping. Do not
fetch details for every hit — a search returning 50 papers does not justify 50
calls.

## 3. Expand from the best result

Once one clearly relevant paper is identified, `clio-arxiv:find_similar_papers`
on it. This finds neighbours a keyword query misses, and is more productive than
rewording the original search.

## 4. Export the bibliography

`clio-arxiv:export_to_bibtex` over the final set. Do this before fetching PDFs:
the bibliography is the deliverable, the PDFs are optional bulk.

`clio-arxiv:download_paper_pdf` only when the user wants the full text. For a
link rather than a file, `clio-arxiv:get_pdf_url` avoids the download entirely.

## 5. Follow the work to its data

Papers describe datasets; the National Data Platform may hold them.

1. `clio-ndp:search_datasets` using terms from the papers — instrument names,
   campaign names and locations work better than paper titles.
2. `clio-ndp:get_dataset_details` on candidates, to check coverage and format
   before committing to a download.
3. `clio-ndp:stage_resource` to bring a file local.

Once staged, the file is an ordinary local dataset — hand it to the
`analyzing-scientific-datasets` skill rather than analysing it here.

## What not to do

- Do not call `get_paper_details` across a whole result set.
- Do not download PDFs when the user asked for a bibliography.
- Do not search NDP with paper titles; search with the terms the data would be
  catalogued under.
- Do not present a search result as a survey without reading the abstracts.
