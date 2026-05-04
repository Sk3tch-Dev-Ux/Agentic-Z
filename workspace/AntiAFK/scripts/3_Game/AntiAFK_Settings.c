// AntiAFK_Settings
// Centralized tunables for the AntiAFK system. Values are intentionally exposed
// as static constants so admins can adjust them via filepatching on a diag
// server without rebuilding the PBO. All time values are in seconds.
class AntiAFK_Settings
{
	// How long a player must remain motionless before being flagged AFK.
	static const int AFK_THRESHOLD_SECONDS = 600; // 10 minutes

	// How often (server-side) we evaluate movement and apply drain while AFK.
	// PlayerBase already ticks via EOnFrame; this is the cadence we sample at.
	static const float TICK_INTERVAL_SECONDS = 1.0;

	// Squared distance threshold (m^2) below which we treat the player as
	// "not moved" between samples. Squared to avoid a sqrt every tick.
	// 0.25 == 0.5 m of jitter tolerance, which absorbs ragdoll/idle sway.
	static const float MOVE_EPSILON_SQ = 0.25;

	// Drain rates applied per tick once AFK. Vanilla stat ranges are typically
	// 0..2500 for water/energy; these values fully drain a topped-off player
	// over roughly 30 minutes of continuous AFK time.
	static const float WATER_DRAIN_PER_TICK = 1.5;
	static const float ENERGY_DRAIN_PER_TICK = 1.5;

	// Set true to spew Print() lines describing AFK state transitions.
	// Leave false in production to avoid log spam.
	static const bool DEBUG_LOG = false;
};
