// SalineHealing - mission-side boot log so admins can confirm the mod loaded.
modded class MissionServer
{
	override void OnInit()
	{
		super.OnInit();
		Print("[SalineHealing] Server mission initialised - saline IV heals "
			+ SalineHealing_Constants.HEAL_AMOUNT + " HP on transfer complete.");
	}
}
