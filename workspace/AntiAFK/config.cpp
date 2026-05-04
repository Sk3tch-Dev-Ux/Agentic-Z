class CfgPatches
{
	class AntiAFK
	{
		units[] = {};
		weapons[] = {};
		requiredVersion = 0.1;
		requiredAddons[] =
		{
			"DZ_Data",
			"DZ_Scripts"
		};
		author = "Sk3tch";
		name = "AntiAFK";
		description = "Automated AFK system that drains water/energy from players who haven't moved in 10 minutes.";
	};
};

class CfgMods
{
	class AntiAFK
	{
		dir = "AntiAFK";
		picture = "";
		action = "";
		hideName = 1;
		hidePicture = 1;
		name = "AntiAFK";
		credits = "Sk3tch";
		author = "Sk3tch";
		authorID = "0";
		version = "1.0";
		extra = 0;
		type = "mod";

		dependencies[] = { "Game", "World", "Mission" };

		class defs
		{
			class gameScriptModule
			{
				value = "";
				files[] = { "AntiAFK/scripts/3_Game" };
			};
			class worldScriptModule
			{
				value = "";
				files[] = { "AntiAFK/scripts/4_World" };
			};
			class missionScriptModule
			{
				value = "";
				files[] = { "AntiAFK/scripts/5_Mission" };
			};
		};
	};
};
