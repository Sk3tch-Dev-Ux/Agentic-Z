// SalineHealing - hooks the SalineMdfr player modifier so that finishing a
// saline IV transfusion grants the patient an instant +30 HP bump.
//
// Vanilla flow (verified against P:\scripts\4_world\classes\playermodifiers\modifiers\saline.c):
//   1. Player uses a SalineBagIV via ActionGiveSalineTarget/Self.
//   2. The action attaches a SalineMdfr (ModifierBase) to the player.
//   3. SalineMdfr.OnTick runs each tick, adding small Blood + Water amounts.
//   4. SalineMdfr.DeactivateCondition returns true when attached_time > m_RegenTime.
//   5. SalineMdfr.OnDeactivate(player) fires exactly once at completion.
//
// We override OnDeactivate on the modifier itself - that is THE single moment
// the transfer is acknowledged complete, server-side, with the player ref in
// hand. SalineBag (empty stub) and SalineBagIV (just registers actions) do
// not have any usable lifecycle event for transfer completion.
modded class SalineMdfr
{
	override void OnDeactivate(PlayerBase player)
	{
		super.OnDeactivate(player);

		if (!GetGame() || !GetGame().IsDedicatedServer())
			return;

		if (!player || !player.IsAlive())
			return;

		SalineHealing_HealService.ApplyHeal(player);
	}
}
