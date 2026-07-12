use std::collections::BTreeMap;
use std::time::SystemTime;

use crate::capabilities::CapabilitySet;

#[derive(Debug, Clone)]
pub struct Context {
    pub request_id: String,
    pub user: UserContext,
    pub device: DeviceContext,
    pub locale: LocaleContext,
    pub capabilities: CapabilitySet,
    pub network: NetworkState,
    pub time: SystemTime,
    pub attributes: BTreeMap<String, String>,
}

#[derive(Debug, Clone, Default)]
pub struct UserContext {
    pub user_id: Option<String>,
    pub profile_id: Option<String>,
}

#[derive(Debug, Clone, Default)]
pub struct DeviceContext {
    pub device_id: Option<String>,
    pub device_class: Option<String>,
}

#[derive(Debug, Clone)]
pub struct LocaleContext {
    pub language: String,
    pub region: Option<String>,
}

impl Default for LocaleContext {
    fn default() -> Self {
        Self {
            language: "en".to_string(),
            region: None,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NetworkState {
    Offline,
    Metered,
    Online,
}

