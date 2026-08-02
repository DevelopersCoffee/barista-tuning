# ADR 0015: Enterprise Knowledge Training Boundary

## Status

Accepted

## Decision

The enterprise-knowledge SLM trains stable behavior:

- intent and entity extraction
- constrained metadata retrieval planning
- grounded synthesis with citations
- allowlisted read-only tool selection
- abstention on missing, stale, conflicting, or unauthorized evidence

Enterprise implementation facts, policies, ownership, and live production data do
not become model-owned knowledge. They remain versioned Knowledge Pack or runtime
records and are retrieved for each request.

All training targets use the versioned Enterprise Knowledge Action contract. The
training boundary rejects malformed outputs, arbitrary execution, write-capable tool
calls, and unsupported claims.

Databricks may provide governed Delta metadata tables, evidence storage, lineage,
and semantic indexes. It remains a replaceable storage/publication backend behind
Domain IR and pack contracts; training code does not depend on Databricks libraries
or credentials. A graph database may be added as a versioned serving projection
without becoming a second canonical source of truth.

## Rationale

Implementation metadata and production facts change more frequently than model
weights can be retrained and revalidated. Keeping facts external reduces staleness,
memorization, privacy leakage, and release coupling. A stable structured action
contract lets small models specialize in predictable behavior while deterministic
systems retain authorization, policy, and execution responsibility.

The backend boundary allows organizations already using Databricks to consolidate
governance and retrieval without forcing the framework or other deployments onto a
specific cloud platform.
