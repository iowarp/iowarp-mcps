---
name: building-a-bibliography
description: Use when citations would be assembled by hand or from memory, which invents plausible arXiv ids and author lists that do not exist. Covers BibTeX export, reading lists and related-work sections. Triggers on "bibtex", "cite these", "reference list". Not for exploring a topic; use surveying-literature-and-datasets.
clio-kit:
  bundle: clio-research
  servers: clio-arxiv, clio-ndp
  provenance: designed
  eval-status: trigger-checked
---

# Build a bibliography from records, not from memory

A fabricated citation is the worst failure available here. It is fluent,
correctly formatted, and points at a paper that does not exist. Every entry has
to come from a tool that returned it.

**Never compose a BibTeX entry by hand.** `clio-arxiv:export_to_bibtex` produces
entries from actual search results. Anything else is a plausible-looking
invention, including a "correction" to a real entry.

## Steps

**1. Collect candidates.**

Search by the axis that matches the question — see
`surveying-literature-and-datasets` for which of the seven search tools to use.
For a bibliography specifically, two are unusually useful:

- `clio-arxiv:search_papers_by_author` — for a group's body of work, and for
  finding the rest of a line of research once you have one paper from it.
- `clio-arxiv:find_similar_papers` — takes a paper you already have and finds
  neighbours by its categories and keywords. This is how the survey stops being
  a keyword list and starts covering a field.

**2. Verify each one you intend to cite.**

`clio-arxiv:get_paper_details` for the full record. Check the authors, the year
and the version. A preprint's title and author list change between versions, and
citing v1's title for v3's content is a real error.

**3. Export.**

`clio-arxiv:export_to_bibtex` on the results. Read what comes back: ArXiv
metadata is author-supplied and imperfect. Names, capitalisation in titles, and
journal fields for papers since published all need checking.

**4. Get the PDFs if they will be read.**

`clio-arxiv:get_pdf_url` for a link, `download_paper_pdf` for one file, or
`download_multiple_pdfs` for several — it rate-limits, and a download loop will
get throttled instead.

## Preprints and published versions

An ArXiv entry is a preprint. Some are later published, often with a different
title and always with a different citation. The ArXiv record does not always know
this.

When it matters — a citation in a submission, or a claim resting on peer review —
check with `clio-web:search` for the published version and cite that. Say which
you are citing; the two are not interchangeable, and a reviewer will notice.

## Citing datasets

Data deserves a citation as much as a paper does.
`clio-ndp:get_dataset_details` returns the metadata a citation needs, and many
datasets carry a DOI. A results section resting on data with no citation cannot
be checked by anyone.

## What not to do

- Do not write a BibTeX entry that did not come from a tool.
- Do not "fix" a returned entry from memory — verify it instead.
- Do not cite a paper whose details you have not fetched.
- Do not cite a preprint as published without checking.
- Do not loop single downloads where the concurrent tool exists.
- Do not leave the datasets uncited.
