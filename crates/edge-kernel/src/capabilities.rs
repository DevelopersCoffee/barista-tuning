use std::collections::BTreeSet;

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Capability(pub String);

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct CapabilitySet {
    values: BTreeSet<Capability>,
}

impl CapabilitySet {
    pub fn new(values: impl IntoIterator<Item = Capability>) -> Self {
        Self {
            values: values.into_iter().collect(),
        }
    }

    pub fn contains(&self, capability: &Capability) -> bool {
        self.values.contains(capability)
    }

    pub fn iter(&self) -> impl Iterator<Item = &Capability> {
        self.values.iter()
    }
}
