// SalineHealing - server-side heal application.
//
// Centralised so the heal rule (amount, zone, type, clamping) lives in one
// place and can be re-used if we later add a second item or an admin tool.
class SalineHealing_HealService
{
	// Apply the configured heal to the given player. Server-only.
	static void ApplyHeal(PlayerBase player)
	{
		if (!player)
			return;

		if (!GetGame().IsDedicatedServer())
			return;

		float maxHp = player.GetMaxHealth(SalineHealing_Constants.HEAL_ZONE, SalineHealing_Constants.HEAL_TYPE);
		float curHp = player.GetHealth(SalineHealing_Constants.HEAL_ZONE, SalineHealing_Constants.HEAL_TYPE);

		float headroom = maxHp - curHp;
		if (headroom <= 0)
			return;

		float grant = SalineHealing_Constants.HEAL_AMOUNT;
		if (grant > headroom)
			grant = headroom;

		player.AddHealth(SalineHealing_Constants.HEAL_ZONE, SalineHealing_Constants.HEAL_TYPE, grant);
	}
}
