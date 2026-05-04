// AntiAFK_PlayerBase
// Server-authoritative AFK detection and stat drain.
//
// Design:
//   - Sample player position once per AntiAFK_Settings.TICK_INTERVAL_SECONDS.
//   - If the player has moved more than MOVE_EPSILON_SQ between samples, reset
//     the idle timer.
//   - Once the idle timer crosses AFK_THRESHOLD_SECONDS, mark the player AFK
//     and start applying water/energy drain on every subsequent tick.
//   - The instant the player moves again, clear the AFK flag and stop drain.
//     Vanilla stat regeneration takes over without any extra hooks from us.
//
// Notes:
//   - Runs server-side only. Stats are server-authoritative and the client
//     receives them via existing vanilla synchronization.
//   - We do NOT call SetSynchDirty(); the engine's stat synchronization is
//     unchanged and any work we do here piggy-backs on it.
modded class PlayerBase
{
	protected vector m_AntiAFK_LastPos;
	protected float m_AntiAFK_IdleTime;
	protected float m_AntiAFK_TickAccumulator;
	protected bool m_AntiAFK_IsAFK;
	protected bool m_AntiAFK_Initialized;

	override void EEInit()
	{
		super.EEInit();

		m_AntiAFK_LastPos = GetPosition();
		m_AntiAFK_IdleTime = 0.0;
		m_AntiAFK_TickAccumulator = 0.0;
		m_AntiAFK_IsAFK = false;
		m_AntiAFK_Initialized = true;
	}

	// EOnFrame fires every simulation frame. We accumulate dt and only do real
	// work once per TICK_INTERVAL_SECONDS to keep the cost negligible.
	override void EOnFrame(IEntity other, float timeSlice)
	{
		super.EOnFrame(other, timeSlice);

		if (!GetGame().IsServer())
			return;

		if (!m_AntiAFK_Initialized)
			return;

		if (!IsAlive())
			return;

		m_AntiAFK_TickAccumulator += timeSlice;
		if (m_AntiAFK_TickAccumulator < AntiAFK_Settings.TICK_INTERVAL_SECONDS)
			return;

		float dt = m_AntiAFK_TickAccumulator;
		m_AntiAFK_TickAccumulator = 0.0;

		AntiAFK_EvaluateIdle(dt);
	}

	// Compare current position to the last sample. If the player moved more
	// than the epsilon, reset idle state. Otherwise advance the idle timer
	// and (if past threshold) apply drain.
	protected void AntiAFK_EvaluateIdle(float dt)
	{
		vector currentPos = GetPosition();
		vector delta = currentPos - m_AntiAFK_LastPos;
		float distSq = delta[0] * delta[0] + delta[1] * delta[1] + delta[2] * delta[2];

		if (distSq > AntiAFK_Settings.MOVE_EPSILON_SQ)
		{
			// Player moved — clear AFK state.
			if (m_AntiAFK_IsAFK)
				AntiAFK_OnExitAFK();

			m_AntiAFK_IdleTime = 0.0;
			m_AntiAFK_LastPos = currentPos;
			return;
		}

		// Player has not moved meaningfully this tick.
		m_AntiAFK_IdleTime += dt;

		if (!m_AntiAFK_IsAFK && m_AntiAFK_IdleTime >= AntiAFK_Settings.AFK_THRESHOLD_SECONDS)
			AntiAFK_OnEnterAFK();

		if (m_AntiAFK_IsAFK)
			AntiAFK_ApplyDrain();
	}

	protected void AntiAFK_OnEnterAFK()
	{
		m_AntiAFK_IsAFK = true;
		if (AntiAFK_Settings.DEBUG_LOG)
			Print("[AntiAFK] Player " + GetIdentity().GetName() + " flagged AFK.");
	}

	protected void AntiAFK_OnExitAFK()
	{
		m_AntiAFK_IsAFK = false;
		if (AntiAFK_Settings.DEBUG_LOG)
			Print("[AntiAFK] Player " + GetIdentity().GetName() + " no longer AFK.");
	}

	// Subtract from the water and energy stats. Vanilla stats clamp at 0,
	// so once both hit zero the player will start taking the usual
	// dehydration/starvation damage and eventually die — exactly the
	// designed outcome.
	protected void AntiAFK_ApplyDrain()
	{
		PlayerStat<float> waterStat = GetStatWater();
		if (waterStat)
			waterStat.Add(-AntiAFK_Settings.WATER_DRAIN_PER_TICK);

		PlayerStat<float> energyStat = GetStatEnergy();
		if (energyStat)
			energyStat.Add(-AntiAFK_Settings.ENERGY_DRAIN_PER_TICK);
	}

	// Public read-only accessor for tooling / future admin commands.
	bool AntiAFK_IsPlayerAFK()
	{
		return m_AntiAFK_IsAFK;
	}

	float AntiAFK_GetIdleSeconds()
	{
		return m_AntiAFK_IdleTime;
	}
};
