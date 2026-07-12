# ADR 0010: Use-Case API

## Status

Accepted

## Decision

The public SDK exposes use cases, not engines. Domain services provide methods
such as search, play, recommend, resume, browse, history, and favorites.

## Rationale

Applications should not know whether the SDK used intent parsing, search,
recommendation, profile signals, or repositories to satisfy a request.

