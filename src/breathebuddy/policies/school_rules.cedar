// BreatheBuddy school bad-day rules (Cedar).
// Read by both the real Cedar engine (via cedarpy) and the built-in fallback
// evaluator in policy.py. Context fields provided at evaluation time:
//   context.predicted_aqi : number
//   context.masks_available : bool
//   context.time_limit_minutes : number

// --- Regular classes: allowed until hazardous -------------------------
permit (principal, action == Action::"hold_classes", resource)
when { context.predicted_aqi < 301 };

forbid (principal, action == Action::"hold_classes", resource)
when { context.predicted_aqi > 300 };

// --- Outdoor assembly: blocked above AQI 150 --------------------------
permit (principal, action == Action::"hold_outdoor_assembly", resource)
when { context.predicted_aqi < 151 };

forbid (principal, action == Action::"hold_outdoor_assembly", resource)
when { context.predicted_aqi > 150 };

// --- Physical education (PE) ------------------------------------------
// Clean air: always fine. Moderate air: only with masks + a time limit.
permit (principal, action == Action::"hold_physical_education", resource)
when { context.predicted_aqi < 151 };

permit (principal, action == Action::"hold_physical_education", resource)
when { context.predicted_aqi <= 200 && context.masks_available == true && context.time_limit_minutes <= 60 };

forbid (principal, action == Action::"hold_physical_education", resource)
when { context.predicted_aqi > 150 && context.masks_available == false };

forbid (principal, action == Action::"hold_physical_education", resource)
when { context.predicted_aqi > 200 };

// --- Indoor activities: the safe fallback -----------------------------
permit (principal, action == Action::"indoor_activities", resource)
when { context.predicted_aqi < 301 };

permit (principal, action == Action::"indoor_activities", resource)
when { context.predicted_aqi > 300 };

// --- Close school / remote learning -----------------------------------
permit (principal, action == Action::"close_school", resource)
when { context.predicted_aqi > 300 };
