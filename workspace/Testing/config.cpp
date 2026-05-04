class CfgPatches
{
    class Testing
    {
        units[] = {};
        weapons[] = {};
        requiredVersion = 0.1;
        requiredAddons[] = {"DZ_Data"};
    };
};

class CfgMods
{
    class Testing
    {
        dir = "Testing";
        picture = "";
        action = "";
        hideName = 1;
        hidePicture = 1;
        name = "Testing";
        credits = "Sk3tch";
        author = "Sk3tch";
        authorID = "0";
        version = "1.0";
        extra = 0;
        type = "mod";

        dependencies[] = {"Game", "World", "Mission"};

        class defs
        {
            class gameScriptModule
            {
                value = "";
                files[] = {"Testing/scripts/3_Game"};
            };
            class worldScriptModule
            {
                value = "";
                files[] = {"Testing/scripts/4_World"};
            };
            class missionScriptModule
            {
                value = "";
                files[] = {"Testing/scripts/5_Mission"};
            };
        };
    };
};
