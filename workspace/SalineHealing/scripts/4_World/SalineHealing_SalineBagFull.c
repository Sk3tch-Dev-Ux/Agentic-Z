// SalineHealing - patches the empty saline bag's transfer-complete path so
// that finishing a SalineBag IV instantly grants the patient 30 HP.
//
// Vanilla flow (DayZ 1.x):
//   * Player attaches a SalineBag_Full to the IV slot.
//   * Quantity decrements over time on the server (TransferValues / agents).
//   * When quantity hits zero the item is replaced/converted to SalineBag
//     (empty) via the standard transfusion pipeline.
//
// We hook AfterStoreLoad / OnQuantityChanged on the FULL bag and detect the
// transition to empty while the bag is attached to a PlayerBase. That is
// the single moment the heal should fire, and only on the server.
modded class SalineBag
{
	protected bool m_SalineHealing_HealApplied;

	override void OnQuantityChanged(float delta)
	{
		super.OnQuantityChanged(delta);

		if (!GetGame() || !GetGame().IsDedicatedServer())
			return;

		if (m_SalineHealing_HealApplied)
			return;

		if (GetQuantity() > 0)
			return;

		// Quantity has reached zero. Find the player this bag is attached to.
		EntityAI parent = GetHierarchyParent();
		if (!parent)
			return;

		PlayerBase player = PlayerBase.Cast(parent);
		if (!player)
			return;

		if (!player.IsAlive())
			return;

		SalineHealing_HealService.ApplyHeal(player);
		m_SalineHealing_HealApplied = true;
	}
}
