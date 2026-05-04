// AntiAFK_MissionServer
// Server-side mission hook. Currently only emits a one-shot startup banner so
// admins can confirm in their RPT that the AntiAFK module loaded. All
// per-player logic lives in AntiAFK_PlayerBase; we deliberately do NOT keep
// our own player list here — PlayerBase.EOnFrame already gives us a per-player
// tick for free.
modded class MissionServer
{
	override void OnInit()
	{
		super.OnInit();

		Print("[AntiAFK] MissionServer initialized. Threshold = "
			+ AntiAFK_Settings.AFK_THRESHOLD_SECONDS + "s, drain water/energy = "
			+ AntiAFK_Settings.WATER_DRAIN_PER_TICK + "/"
			+ AntiAFK_Settings.ENERGY_DRAIN_PER_TICK + " per tick.");
	}
};
