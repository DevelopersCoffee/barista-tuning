# ADR 0004: Media IR

## Status

Accepted

## Decision

Media IR is an immutable, independently versioned schema. Runtime media packs
must compile provider-specific data into this representation.

## Rationale

A stable IR lets IPTV, YouTube, Jellyfin, Plex, and local files coexist without
changing runtime use-case APIs.

