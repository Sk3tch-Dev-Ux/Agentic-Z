class CfgPatches
{
	class SalineHealing
	{
		units[] = {};
		weapons[] = {};
		requiredVersion = 0.1;
		requiredAddons[] =
		{
			"DZ_Data",
			"DZ_Scripts",
			"DZ_Gear_Medical"
		};
		author = "Sk3tch";
		name = "SalineHealing";
		version = "1.0.0";
	};
};

class CfgMods
{
	class SalineHealing
	{
		dir = "SalineHealing";
		picture = "";
		action = "";
		hideName = 0;
		hidePicture = 0;
		name = "SalineHealing";
		credits = "Sk3tch";
		author = "Sk3tch";
		authorID = "0";
		version = "1.0.0";
		extra = 0;
		type = "mod";

		dependencies[] = { "Game", "World", "Mission" };

		class defs
		{
			class gameScriptModule
			{
				value = "";
				files[] = { "SalineHealing/scripts/3_Game" };
			};

			class worldScriptModule
			{
				value = "";
				files[] = { "SalineHealing/scripts/4_World" };
			};

			class missionScriptModule
			{
				value = "";
				files[] = { "SalineHealing/scripts/5_Mission" };
			};
		};
	};
};
