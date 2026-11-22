//! The bridge's simulator seam (roadmaps 035, 046): the [`SimBackend`] trait and its types
//! (`scensim_core::sim`), and the one implementation, [`remote::RemoteBackend`], which drives a
//! world server over the world protocol. The coordinator's tests run on `scensim_core::fake`.

pub use scensim_core::sim::*;

#[cfg(test)]
pub use scensim_core::fake;

pub mod remote;

/// What the bridge's own services ask of its backend beyond SSv2's protocol.
pub trait BridgeBackend: SimBackend {
    /// `~/load_map` (roadmap 077, G9): load the world of the map at `lanelet2_map_path` now,
    /// between scenarios, as an `Initialize` would, so the vehicle stacks started next find
    /// it; what was loaded, for the reply.
    fn load_map(&mut self, lanelet2_map_path: &str) -> Result<String, BackendError>;
    /// `~/set_knob_profiles` (roadmap 092 K9): the run's knob profiles, JSON
    /// (`remote::profiles`), replacing the last run's; what was set, for the reply.
    fn set_knob_profiles(&mut self, json: &str) -> Result<String, BackendError>;
}

/// The fake loads a map as it initializes, at the default step.
#[cfg(test)]
impl BridgeBackend for fake::FakeBackend {
    fn load_map(&mut self, lanelet2_map_path: &str) -> Result<String, BackendError> {
        self.initialize(&Episode {
            step_time: 0.05,
            realtime_factor: 1.0,
            lanelet2_map_path: lanelet2_map_path.to_string(),
        })?;
        Ok(format!("loaded {lanelet2_map_path}"))
    }
    fn set_knob_profiles(&mut self, json: &str) -> Result<String, BackendError> {
        let p = remote::profiles::parse(json).map_err(BackendError::Failed)?;
        Ok(format!("{} knob profile(s)", p.len()))
    }
}
