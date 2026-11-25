//! Knob profiles (scensim roadmap 092 K9; docs/design/scenario-description.md section 3): a
//! world knob whose value changes over a run, along the scenario's simulation time or the ego's
//! lane position on a lane anchor, piecewise linear between breakpoints. `scensim run` sends a
//! run's profiles before SSv2 starts (`~/set_knob_profiles`, JSON); each frame the bridge
//! evaluates them and sends the world a `SetEnvironment` with the fields that moved by at least
//! their step since the last send, and records each knob's commanded and read-back value in
//! the gap trace (its `knob` line).
//!
//! ```json
//! {"profiles": [{"knob": "visibility", "field": "fog_visual_range", "step": 9.5,
//!                "coordinate": "time", "points": [[0, 1000], [12, 1000], [20, 80]]},
//!               {"knob": "visibility", "field": "fog_visual_range", "step": 9.5,
//!                "coordinate": {"lane": "west_street", "s": [0, 0.5], "x": [..], "y": [..]},
//!                "points": [[0, 1000], [200, 1000], [300, 80]]}]}
//! ```

use serde::Deserialize;

use crate::environment::{Precipitation, PrecipitationType, ScenarioWeather, Sun};

/// The scenario-environment field a profile sets, in `ScenarioWeather`'s units.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Field {
    /// m
    FogVisualRange,
    /// rad above the horizon (the azimuth of a sun not yet placed: 0)
    SunElevation,
    /// rad clockwise from north (the elevation of a sun not yet placed: 0.5 rad)
    SunAzimuth,
    /// mm/h of rain (0: dry)
    PrecipitationIntensity,
    /// oktas, 0 to 8 (rounded)
    CloudCoverOktas,
}

impl Field {
    /// The field's value in a read-back, if the world gave that part.
    pub fn read(self, w: &ScenarioWeather) -> Option<f64> {
        match self {
            Field::FogVisualRange => w.fog_visual_range,
            Field::SunElevation => w.sun.map(|s| s.elevation),
            Field::SunAzimuth => w.sun.map(|s| s.azimuth),
            Field::PrecipitationIntensity => w.precipitation.map(|p| p.intensity),
            Field::CloudCoverOktas => w.cloud_cover_oktas.map(f64::from),
        }
    }

    /// `v` laid into `w` (a sun keeps the other angle it has).
    pub fn write(self, v: f64, w: &mut ScenarioWeather) {
        match self {
            Field::FogVisualRange => w.fog_visual_range = Some(v),
            Field::SunElevation => {
                let az = w.sun.map_or(0.0, |s| s.azimuth);
                w.sun = Some(Sun {
                    azimuth: az,
                    elevation: v,
                    illuminance: 0.0,
                })
            }
            Field::SunAzimuth => {
                let el = w.sun.map_or(0.5, |s| s.elevation);
                w.sun = Some(Sun {
                    azimuth: v,
                    elevation: el,
                    illuminance: 0.0,
                })
            }
            Field::PrecipitationIntensity => {
                w.precipitation = Some(Precipitation {
                    kind: if v > 0.0 {
                        PrecipitationType::Rain
                    } else {
                        PrecipitationType::Dry
                    },
                    intensity: v.max(0.0),
                })
            }
            Field::CloudCoverOktas => w.cloud_cover_oktas = Some(v.round().clamp(0.0, 8.0) as u8),
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
struct LaneIn {
    lane: String,
    s: Vec<f64>,
    x: Vec<f64>,
    y: Vec<f64>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(untagged)]
enum CoordinateIn {
    Named(String),
    Lane(LaneIn),
}

#[derive(Debug, Clone, Deserialize)]
struct ProfileIn {
    knob: String,
    field: Field,
    step: f64,
    /// s of scenario time between two sends (a crossed breakpoint still sends at once);
    /// absent: none
    #[serde(default)]
    min_interval: f64,
    coordinate: CoordinateIn,
    points: Vec<[f64; 2]>,
}

#[derive(Debug, Clone, Deserialize)]
struct ProfilesIn {
    profiles: Vec<ProfileIn>,
}

/// What a profile's value runs along.
#[derive(Debug, Clone, PartialEq)]
pub enum Coordinate {
    /// SSv2's scenario time (UpdateFrame's `current_simulation_time`), s: from 0 at the
    /// scenario's start, not the world's clock (which carries the 1000 s base).
    Time,
    /// The ego's lane position on a lane anchor: its centreline, s and x, y (map frame).
    Lane {
        name: String,
        s: Vec<f64>,
        xy: Vec<[f64; 2]>,
    },
}

#[derive(Debug, Clone, PartialEq)]
pub struct Profile {
    pub knob: String,
    pub field: Field,
    pub step: f64,
    /// s of scenario time between two sends: a `SetEnvironment` costs the frame it is sent
    /// in (CARLA, 2026-11-22: frame p95 6 ms without, 20-220 ms with one every frame)
    pub min_interval: f64,
    pub coordinate: Coordinate,
    pub points: Vec<(f64, f64)>,
}

/// How far ahead and behind the ego's last lane position its next one is looked for, m: a lane
/// that crosses itself (or passes near itself) is not read at the wrong pass.
const LANE_AHEAD: f64 = 50.0;
const LANE_BEHIND: f64 = 20.0;

impl Profile {
    /// The value at coordinate `x`: linear between breakpoints, held beyond the ends.
    pub fn value_at(&self, x: f64) -> f64 {
        let p = &self.points;
        if x <= p[0].0 {
            return p[0].1;
        }
        for w in p.windows(2) {
            let ((x0, v0), (x1, v1)) = (w[0], w[1]);
            if x <= x1 {
                return if x1 > x0 {
                    v0 + (v1 - v0) * (x - x0) / (x1 - x0)
                } else {
                    v1
                };
            }
        }
        p[p.len() - 1].1
    }

    /// The ego's lane position on this profile's lane: the nearest point of its centreline,
    /// near `last` when there is one, else anywhere. None for a time profile.
    pub fn lane_position(&self, ego: [f64; 2], last: Option<f64>) -> Option<f64> {
        let Coordinate::Lane { s, xy, .. } = &self.coordinate else {
            return None;
        };
        let mut best: Option<(f64, f64)> = None; // (distance², s)
        for i in 0..xy.len().saturating_sub(1) {
            if let Some(l) = last {
                if s[i + 1] < l - LANE_BEHIND || s[i] > l + LANE_AHEAD {
                    continue;
                }
            }
            let (a, b) = (xy[i], xy[i + 1]);
            let (dx, dy) = (b[0] - a[0], b[1] - a[1]);
            let len2 = dx * dx + dy * dy;
            let t = if len2 > 0.0 {
                (((ego[0] - a[0]) * dx + (ego[1] - a[1]) * dy) / len2).clamp(0.0, 1.0)
            } else {
                0.0
            };
            let (px, py) = (a[0] + t * dx, a[1] + t * dy);
            let d2 = (ego[0] - px).powi(2) + (ego[1] - py).powi(2);
            if best.is_none_or(|(b2, _)| d2 < b2) {
                best = Some((d2, s[i] + t * (s[i + 1] - s[i])));
            }
        }
        match (best, last) {
            (None, Some(_)) => self.lane_position(ego, None),
            (b, _) => b.map(|(_, s)| s),
        }
    }
}

/// `~/set_knob_profiles`'s JSON, checked: every problem, one per line.
pub fn parse(json: &str) -> Result<Vec<Profile>, String> {
    let doc: ProfilesIn = serde_json::from_str(json)
        .map_err(|e| format!("knob profiles: not the expected JSON: {e}"))?;
    let mut out = Vec::new();
    let mut problems = Vec::new();
    for (i, p) in doc.profiles.into_iter().enumerate() {
        let at = format!("profiles[{i}] ({})", p.knob);
        if p.knob.is_empty() {
            problems.push(format!("{at}: no knob name"));
        }
        if !(p.step.is_finite() && p.step > 0.0) {
            problems.push(format!("{at}: step {} is not a positive number", p.step));
        }
        if !(p.min_interval.is_finite() && p.min_interval >= 0.0) {
            problems.push(format!(
                "{at}: min_interval {} is not a number >= 0",
                p.min_interval
            ));
        }
        if p.points.is_empty() {
            problems.push(format!("{at}: no breakpoints"));
        }
        if p.points.iter().flatten().any(|v| !v.is_finite()) {
            problems.push(format!("{at}: a breakpoint is not finite"));
        }
        if p.points.windows(2).any(|w| w[1][0] < w[0][0]) {
            problems.push(format!("{at}: breakpoints do not increase"));
        }
        let coordinate = match p.coordinate {
            CoordinateIn::Named(n) if n == "time" => Coordinate::Time,
            CoordinateIn::Named(n) => {
                problems.push(format!("{at}: coordinate {n:?}: \"time\" or a lane"));
                continue;
            }
            CoordinateIn::Lane(l) => {
                if l.s.len() < 2 || l.s.len() != l.x.len() || l.s.len() != l.y.len() {
                    problems.push(format!(
                        "{at}: lane {}: s, x and y of one length, two or more",
                        l.lane
                    ));
                    continue;
                }
                if l.s.windows(2).any(|w| w[1] < w[0]) {
                    problems.push(format!("{at}: lane {}: s does not increase", l.lane));
                    continue;
                }
                Coordinate::Lane {
                    name: l.lane,
                    xy: l.x.iter().zip(&l.y).map(|(x, y)| [*x, *y]).collect(),
                    s: l.s,
                }
            }
        };
        out.push(Profile {
            knob: p.knob,
            field: p.field,
            step: p.step,
            min_interval: p.min_interval,
            coordinate,
            points: p.points.iter().map(|v| (v[0], v[1])).collect(),
        });
    }
    let mut seen: Vec<Field> = Vec::new();
    for p in &out {
        if seen.contains(&p.field) {
            problems.push(format!(
                "two profiles set {:?}: one knob per field",
                p.field
            ));
        }
        seen.push(p.field);
    }
    if problems.is_empty() {
        Ok(out)
    } else {
        Err(problems.join("\n"))
    }
}

/// A profile as the backend runs it: what it last sent and what the world read back.
#[derive(Debug, Clone)]
pub struct Active {
    pub profile: Profile,
    pub last_sent: Option<f64>,
    /// The scenario time of the last send.
    pub last_sent_at: Option<f64>,
    pub applied: Option<f64>,
    pub last_s: Option<f64>,
    /// The coordinate at the last frame: a breakpoint crossed since is sent at once.
    pub last_x: Option<f64>,
    /// Sends so far: the first is repeated on the next frame (issue 171), since a world may
    /// read back the value before it until it has ticked (CARLA 0.9.16's `get_weather` right
    /// after `set_weather`), and only the repeat's read-back follows a tick.
    pub sends: u32,
}

impl Active {
    pub fn new(profile: Profile) -> Self {
        Self {
            profile,
            last_sent: None,
            last_sent_at: None,
            applied: None,
            last_s: None,
            last_x: None,
            sends: 0,
        }
    }

    /// This frame's commanded value (`sim_time`, s; the ego's map position, if known), and
    /// whether it is to be sent: the first frame and the one after it (the first send repeated,
    /// issue 171), a value moved by the step since the last send, or a breakpoint crossed since
    /// the last frame (so a ramp's end, or a plateau, is reached within a frame, never left up
    /// to a step short). A lane profile with no ego pose holds its first value.
    pub fn commanded(&mut self, sim_time: f64, ego: Option<[f64; 2]>) -> (f64, bool) {
        let x = match &self.profile.coordinate {
            Coordinate::Time => Some(sim_time),
            Coordinate::Lane { .. } => ego.and_then(|e| self.profile.lane_position(e, self.last_s)),
        };
        if let Some(s) = x.filter(|_| matches!(self.profile.coordinate, Coordinate::Lane { .. })) {
            self.last_s = Some(s);
        }
        let v = match x {
            Some(x) => self.profile.value_at(x),
            None => self.profile.points[0].1,
        };
        let crossed = match (self.last_x, x) {
            (Some(a), Some(b)) => self
                .profile
                .points
                .iter()
                .any(|(px, _)| (a < *px && *px <= b) || (b <= *px && *px < a)),
            _ => false,
        };
        if x.is_some() {
            self.last_x = x;
        }
        let due = self
            .last_sent_at
            .is_none_or(|t0| sim_time - t0 >= self.profile.min_interval - 1e-9);
        let send = self.sends == 1
            || self.last_sent.is_none_or(|l| {
                ((v - l).abs() >= self.profile.step && due)
                    || (crossed && (v - l).abs() > 1e-9 * l.abs().max(1.0))
            });
        (v, send)
    }

    /// The bridge sent `v` at scenario time `t`.
    pub fn mark_sent(&mut self, v: f64, t: f64) {
        self.last_sent = Some(v);
        self.last_sent_at = Some(t);
        self.sends += 1;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn issue_171_the_first_send_is_repeated_on_the_next_frame_and_then_held() {
        // a constant (092 K9e's environment: form): sent on frames 1 and 2, then never
        let mut a = Active::new(
            parse(
                r#"{"profiles": [{"knob": "illumination.sun_elevation", "field": "sun_elevation",
                    "step": 0.001, "coordinate": "time", "points": [[0, 1.0472]]}]}"#,
            )
            .unwrap()
            .remove(0),
        );
        let mut sent = Vec::new();
        for f in 0..10 {
            let t = f as f64 * 0.05;
            let (v, send) = a.commanded(t, None);
            assert!((v - 1.0472).abs() < 1e-12);
            if send {
                a.mark_sent(v, t);
                sent.push(f);
            }
        }
        assert_eq!(sent, vec![0, 1]);
    }

    fn fog_time() -> Profile {
        parse(
            r#"{"profiles": [{"knob": "visibility", "field": "fog_visual_range", "step": 10,
                "coordinate": "time", "points": [[0, 1000], [10, 1000], [20, 80]]}]}"#,
        )
        .unwrap()
        .remove(0)
    }

    #[test]
    fn a_profile_is_linear_between_breakpoints_and_held_beyond() {
        let p = fog_time();
        assert_eq!(p.value_at(-1.0), 1000.0);
        assert_eq!(p.value_at(10.0), 1000.0);
        assert!((p.value_at(15.0) - 540.0).abs() < 1e-9);
        assert_eq!(p.value_at(25.0), 80.0);
    }

    #[test]
    fn a_value_is_sent_first_and_then_when_it_moved_by_the_step() {
        let mut a = Active::new(fog_time());
        let mut sent = Vec::new();
        for f in 0..=400 {
            let t = f64::from(f) * 0.05;
            let (v, send) = a.commanded(t, None);
            if send {
                a.mark_sent(v, t);
                sent.push((t, v));
            }
        }
        // the first frame, then whenever the 920 m ramp over 10 s (4.6 m a frame) has moved
        // the 10 m step: each send at least the step and at most the step and a frame's change
        // after the last, the last at the ramp's end
        assert_eq!(sent[0], (0.0, 1000.0));
        for w in sent[..sent.len() - 1].windows(2) {
            let d = (w[1].1 - w[0].1).abs();
            assert!((10.0 - 1e-9..10.0 + 4.6 + 1e-9).contains(&d), "{w:?}");
        }
        // the ramp's end (a breakpoint) is sent exactly, though within a step of the last send
        assert_eq!(sent.last().unwrap().1, 80.0);
        assert_eq!(sent.len(), 68);
    }

    #[test]
    fn min_interval_spaces_the_sends_but_not_a_breakpoint() {
        let mut p = fog_time();
        p.min_interval = 1.0;
        let mut a = Active::new(p);
        let mut sent = Vec::new();
        for f in 0..=500 {
            let t = f64::from(f) * 0.05;
            let (v, send) = a.commanded(t, None);
            if send {
                a.mark_sent(v, t);
                sent.push((t, v));
            }
        }
        // the first frame, one a second along the 10 s ramp, and the ramp's end at once
        assert!(sent[1..sent.len() - 1]
            .windows(2)
            .all(|w| w[1].0 - w[0].0 >= 1.0 - 1e-9));
        assert_eq!(sent.last().unwrap().1, 80.0);
        assert!((10..=13).contains(&sent.len()), "{sent:?}");
    }

    #[test]
    fn a_lane_profile_reads_the_egos_lane_position_near_its_last() {
        // a lane east along y = 0 for 100 m, then back west along y = 4 (a U): at x = 10 the
        // ego is at s 10 going out and s 190 coming back
        let mut s = Vec::new();
        let mut x = Vec::new();
        let mut y = Vec::new();
        for k in 0..=100 {
            s.push(f64::from(k));
            x.push(f64::from(k));
            y.push(0.0);
        }
        for k in 1..=100 {
            s.push(100.0 + 4.0 + f64::from(k));
            x.push(100.0 - f64::from(k));
            y.push(4.0);
        }
        let json = serde_json::json!({"profiles": [{"knob": "visibility",
            "field": "fog_visual_range", "step": 1.0,
            "coordinate": {"lane": "u", "s": s, "x": x, "y": y},
            "points": [[0, 1000], [200, 0]]}]});
        let p = parse(&json.to_string()).unwrap().remove(0);
        assert!((p.lane_position([10.0, 0.5], None).unwrap() - 10.0).abs() < 1e-9);
        // near the far pass, but last seen at s 180: the far pass, not the near one
        assert!((p.lane_position([10.0, 2.5], Some(185.0)).unwrap() - 194.0).abs() < 1e-9);
        let mut a = Active::new(p);
        let (v, send) = a.commanded(0.0, Some([50.0, 0.0]));
        assert!(send && (v - 750.0).abs() < 1e-9);
        let (v, _) = a.commanded(0.0, None);
        assert_eq!(v, 1000.0); // no ego: the first value
    }

    #[test]
    fn a_field_reads_and_writes_its_part() {
        let mut w = ScenarioWeather::default();
        Field::SunElevation.write(0.2, &mut w);
        Field::SunAzimuth.write(1.0, &mut w);
        assert_eq!(Field::SunElevation.read(&w), Some(0.2));
        assert_eq!(Field::SunAzimuth.read(&w), Some(1.0));
        Field::PrecipitationIntensity.write(0.0, &mut w);
        assert_eq!(w.precipitation.unwrap().kind, PrecipitationType::Dry);
        Field::CloudCoverOktas.write(11.0, &mut w);
        assert_eq!(w.cloud_cover_oktas, Some(8));
        assert_eq!(Field::FogVisualRange.read(&w), None);
    }

    #[test]
    fn bad_profiles_are_refused_with_every_problem() {
        let e = parse(
            r#"{"profiles": [
                {"knob": "a", "field": "fog_visual_range", "step": 0, "coordinate": "time",
                 "points": [[5, 1], [1, 2]]},
                {"knob": "b", "field": "fog_visual_range", "step": 1, "coordinate": "route",
                 "points": [[0, 1]]}]}"#,
        )
        .unwrap_err();
        assert!(e.contains("step 0 is not a positive number"), "{e}");
        assert!(e.contains("breakpoints do not increase"), "{e}");
        assert!(e.contains("coordinate \"route\""), "{e}");
        let e = parse(
            r#"{"profiles": [
                {"knob": "a", "field": "fog_visual_range", "step": 1, "coordinate": "time", "points": [[0, 1]]},
                {"knob": "b", "field": "fog_visual_range", "step": 1, "coordinate": "time", "points": [[0, 1]]}]}"#,
        )
        .unwrap_err();
        assert!(e.contains("one knob per field"), "{e}");
        assert!(parse(r#"{"profiles": []}"#).unwrap().is_empty());
    }
}
