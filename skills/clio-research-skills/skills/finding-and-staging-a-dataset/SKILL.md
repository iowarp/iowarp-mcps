---
name: finding-and-staging-a-dataset
description: Use when analysis would be attempted on a dataset that exists only as a search result and has no path on disk yet, so every later read fails on a file that was never staged. Triggers on "find a dataset", "download the data", "stage this". Not for the papers behind the data; use surveying-literature-and-datasets.
clio-kit:
  bundle: clio-research
  servers: clio-ndp, clio-scientific-catalog, clio-web
  provenance: designed
  eval-status: trigger-checked
---

# Find data, then get it onto disk

Two catalogs answer "where is data about X", and they hold different things. The
step everyone forgets is the last one: a dataset that has only been *found* is
metadata. Nothing can read it until it is staged.

## Which catalog

**`clio-ndp`** — the National Data Platform. Public, broad, organised by
publishing organisation.

**`clio-scientific-catalog`** — datasets an operator has registered on this
deployment. Narrower, curated, and the one that knows about local data the public
platform has never heard of.

Search both when the answer matters. They do not overlap in any predictable way.

## National Data Platform

1. `clio-ndp:list_organizations` — who publishes here. On a broad topic this
   narrows the search far more effectively than more keywords.
2. `clio-ndp:search_datasets` — term-based or field-specific.
3. `clio-ndp:get_dataset_details` — the full metadata for one. **Read this before
   staging.** It says what the data actually is, and staging is the step that
   costs time and disk.
4. `clio-ndp:stage_resource` — download an HTTP(S) or OSDF/Pelican resource,
   returning `local_path`, size, and content type.

`local_path` is the whole point. It is what you pass to the readers — see
`exploring-an-unfamiliar-dataset`. The returned content type tells you which
reader: a `.gz` needs decompressing first, a `.parquet` goes to the Parquet
server, an `.h5` to HDF5.

## The operator catalog, and its handoff to a pipeline

`clio-scientific-catalog:scientific_dataset_search` returns bounded intrinsic
summaries. `scientific_dataset_describe` returns one exact record plus a
top-level `dataset_descriptor`.

> Pass `dataset_descriptor` **unchanged** as `config.dataset_descriptor` to
> `clio-jarvis:jarvis_add_step`. Do not rebuild it, do not extract a path from
> it, do not simplify it. It is the identifier the pipeline resolves; anything
> derived from it loses what makes the reference exact.

This is the same shape as the Spack handoff in
`running-a-simulation-on-a-cluster`: an opaque token that must survive the trip
intact. Reconstructing it is the failure both times.

So there are two routes for operator-registered data: stage it and read it
directly, or hand the descriptor to a pipeline and let the pipeline resolve it.
Use the second when the data feeds a run rather than an inspection.

## Check size before staging

`get_dataset_details` reports what you are about to download. Staging a large
dataset to answer a question the metadata already answers is pure cost, and on a
shared filesystem it is someone else's cost too.

## What not to do

- Do not search only one catalog when the answer matters.
- Do not stage before reading the details.
- Do not try to analyse a dataset that has not been staged — there is no path
  until then.
- Do not rebuild or extract from a `dataset_descriptor`; pass it through.
- Do not ignore the returned content type when choosing a reader.
