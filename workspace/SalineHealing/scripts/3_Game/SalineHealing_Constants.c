// SalineHealing — tunable constants.
// Kept in 3_Game so both client and server symbols see identical values.
class SalineHealing_Constants
{
	// Amount of Health (HP) restored when a saline IV finishes transferring.
	static const float HEAL_AMOUNT = 30.0;

	// Health type targeted by the heal. "Health" = generic HP pool used by
	// the player damage system (see PlayerBase.AddHealth / GetHealth).
	static const string HEAL_ZONE = "";       // empty string = global
	static const string HEAL_TYPE = "Health"; // "Health", "Blood", "Shock"
}
