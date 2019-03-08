from pyquery import PyQuery
import sys
import json
import os
import re

validClassSources = [
    "PHB",
    "XGE"
]

schoolMap = {
    "A": "Abjuration",
    "C": "Conjuration",
    "D": "Divination",
    "E": "Enchantment",
    "V": "Evocation ",
    "I": "Illusion",
    "N": "Necromancy",
    "T": "Transmutation",
}

metaSource = {}

def removeToolCommonMacros(entry):
    return re.sub(r"{@\w+ *([^|}]+)[|]*[^}]*}", r"\1", entry)

def removeToolScaleMacro(entry):
    return re.sub(r"{@\w+ *([^|}]+)[|]*[^}]*[|]([^|}]+)}", r"\2", entry)

def getSpellName(jsonSpell):
    # handle base name
    name = jsonSpell["name"]

    if "meta" in jsonSpell:
        if "ritual" in jsonSpell["meta"] and jsonSpell["meta"]["ritual"] == True:
            name += " (Ritual)"
    
    return name

def getSchoolName(jsonSpell):
    # handle school
    if jsonSpell["school"] in schoolMap:
        return schoolMap[jsonSpell["school"]]

    print("----> unknown school " + jsonSpell["school"])
    return "Unknown"

def getSubtitle(jsonSpell):
    if jsonSpell["level"] == 0:
        return getSchoolName(jsonSpell) + " cantrip"
    else:
        return "Level " + str(jsonSpell["level"]) + " " + getSchoolName(jsonSpell)

def getComponentList(jsonSpell):
    # handle component list
    cObj = jsonSpell["components"]
    componentList = ""
    if "v" in cObj and cObj["v"]:
        componentList += "V"
    
    if "s" in cObj and cObj["s"]:
        componentList += "###S"


    if "m" in cObj:
        if type(cObj["m"]) is str:
            componentList += "###M (" + cObj["m"] + ")"
        elif type(cObj["m"]) is bool:
            componentList += "###M"
        else:
            componentList += "###M (" + cObj["m"]["text"] + ")"

    componentList = re.sub("^###", "", componentList)
    componentList = re.sub("###", ", ", componentList)
    
    return componentList.strip()

def getCastingTime(jsonSpell):
    # handle time
    return str(jsonSpell["time"][0]["number"]) + " "+ jsonSpell["time"][0]["unit"]

def getRange(jsonSpell):
    # handle range
    r = jsonSpell["range"]

    # handle special case
    if r["type"] == "special":
        return "special"

    # create rd var
    rd = r["distance"]

    # handle point case
    if r["type"] == "point":
        if rd["type"] in ["self", "touch", "sight", "unlimited", "plane"]:
            return rd["type"]
        else:
            return str(rd["amount"]) + " " + rd["type"]

    if r["type"] in ["hemisphere"]:
        return "self (" + str(rd["amount"]) + "-" + rd["type"] + " radius " + r["type"] + ")"

    if r["type"] in ["sphere", "radius", "line", "cone", "cube"]:
        return "self (" + str(rd["amount"]) + "-" + rd["type"] + " " + r["type"] + ")"

    print("----> unknown range " + r["type"])
    return r["type"]

def getDuration(jsonSpell):
    d = jsonSpell["duration"][0]
    
    # handle instant case
    if d["type"] == "instant":
        return "instant"

    # handle permanent
    if d["type"] == "permanent":
        if "ends" in d:
            de = d["ends"]
            if "trigger" in de:
                return "Until dispelled or triggered"
            else:
                return "Until dispelled"
        else:
            return "Pernament"

    # handle special
    if d["type"] == "special":
        return "Special"

    # handle timed case
    dd = d["duration"]
    line = ""
    
    ## handle concentration
    if "concentration" in d and d["concentration"]:
        line = "Concentration, up to "

    return line + str(dd["amount"]) + " " + dd["type"]

def getCasterArray(jsonSpell):
    arr = []
    # handle main class
    if "classes" in jsonSpell:
        if "fromClassList" in jsonSpell["classes"]:
            mainList = jsonSpell["classes"]["fromClassList"]
            for c in mainList:
                if c["source"] in validClassSources:
                    arr += [c["name"]]

        if "fromSubclass" in jsonSpell["classes"]:
            # handle subclass
            subList = jsonSpell["classes"]["fromSubclass"]

            for c in subList:
                ccc = c["class"]
                csc = c["subclass"]
                if ccc["source"] in validClassSources and csc["source"] in validClassSources:
                    if "subSubclass" in csc:
                        arr += [ccc["name"] + "-" + csc["name"] + "-" + csc["subSubclass"]]
                    else:
                        arr += [ccc["name"] + "-" + csc["name"]]

    return arr

def getSource(jsonSpell):
    if "source" in jsonSpell:
        source = jsonSpell["source"]

        # check if in meta source
        if source in metaSource:
            source = metaSource[source]

        # add page number if available
        if "page" in jsonSpell:
            return "Page " + str(jsonSpell["page"]) + " of " + source
        else:
            return source.upper()

    return "UNKNOWN"

def getEntries(jsonSpell):
    lines = []
    for entry in jsonSpell["entries"]:
        if type(entry) is str:
            entry = removeToolScaleMacro(entry)
            lines += ["text | " + removeToolCommonMacros(entry)]
        elif entry["type"] == "list":
            for item in entry["items"]:
                item = removeToolScaleMacro(item)
                lines += ["bullet | " + removeToolCommonMacros(item)]
        else:
            lines += ["text | Refer to book for full details."]

    return lines

def getHigherLevel(jsonSpell):
    lines = []
    if "entriesHigherLevel" in jsonSpell:
        for hl in jsonSpell["entriesHigherLevel"]:
            for entry in hl["entries"]:
                if type(entry) is str:
                    entry = removeToolScaleMacro(entry)
                    lines += ["text | " + removeToolCommonMacros(entry)]
                elif entry["type"] == "list":
                    for item in entry["items"]:
                        item = removeToolScaleMacro(item)
                        lines += ["bullet | " + removeToolCommonMacros(item)]
                else:
                    lines += ["text | Refer to book for full details."]
    return lines

def getCasterLine(cArr):
    # handle empty case
    if len(cArr) == 0:
        return ""

    # handle single case
    if len(cArr) == 1:
        return cArr[0]

    # handle double case
    if len(cArr) == 2:
        return cArr[0] + " & " + cArr[1]

    # handle more than 2 case
    line = ""
    for c in cArr:
        line += c + ", "

    ## remove extra characters
    line = line[:-2]
    
    # Replace last comma with an & and maybe a comma
    if line.count(",") > 1:
        line = re.sub(",(?!.*,)", ", &", line)
    elif line.count(",") == 1:
        line = re.sub(",(?!.*,)", " &", line)
    
    return line

def getSpellJsonTool(fileName, selectedSpells):
    with open(fileName, "r", encoding="utf8") as myfile:
        data = json.load(myfile)
        # register meta source
        if "_meta" in data:
            if "sources" in data["_meta"]:
                for dms in data["_meta"]["sources"]:
                    if "json" in dms and "full" in dms:
                        metaSource[dms["json"]] = dms["full"]

        # get spells from data
        if "spell" in data:
            spells = data["spell"]
        else:
            print("ERROR: no spell data found in " + fileName)
            return []
        totalList = []

        for jsonSpell in spells:
            # check that it is in selected spells
            if len(selectedSpells) > 0:
                isValid = False
                for ss in selectedSpells:
                    sameName = jsonSpell["name"].upper() == ss["name"]
                    sameSource = jsonSpell["source"].upper() == ss["source"]
                    if sameName and sameSource:
                        ss["found"] = True
                        isValid = True
                        print("found " + ss["name"] + " from " + ss["source"])
                        break
                
                # check if not found
                if isValid == False:
                    continue

            print("working on " + jsonSpell["name"])
            spell = spell5()
            spell.name = getSpellName(jsonSpell)
            spell.subtitle = getSubtitle(jsonSpell)
            spell.level = str(jsonSpell["level"])
            spell.school = getSchoolName(jsonSpell)
            spell.time = getCastingTime(jsonSpell)
            spell.duration = getDuration(jsonSpell)
            spell.range = getRange(jsonSpell)
            spell.components = getComponentList(jsonSpell)
            spell.entries = getEntries(jsonSpell)
            spell.higherLevel = getHigherLevel(jsonSpell)
            spell.source = getSource(jsonSpell)
            spell.casters = getCasterArray(jsonSpell)

            totalList += [spell.toCardJson()]


        return totalList

class spell5:
    name = "default"
    subtitle = ""
    level = ""
    school = ""
    time = ""
    duration = ""
    range = ""
    components = ""
    entries = ""
    higherLevel = ""
    source = ""
    casters = ""

    def toCardJson(self):
        data = {}

        # add header content
        data["count"] = 1
        data["color"] = "DarkGray"
        data["title"] = self.name
        data["icon"] = "white-book-" + self.level

        # add main content
        data["contents"] = [
            "subtitle | " + self.subtitle,
            "rule",
            "property | Casting time | " + self.time.title(),
            "property | Range | " + self.range.title(),
            "property | Duration | " + self.duration.title(),
            "property | Components | " + self.components,
            "property | Class | " + getCasterLine(self.casters).title(),
            "property | Source | " + self.source,
            "rule",
        ]

        # add entry text
        for entry in self.entries:
            data["contents"] += [entry]

        # add higher level
        if self.higherLevel and len(self.higherLevel) > 0:
            data["contents"] += [
                "fill | 3",
                "section | At higher levels",
            ]
            for entry in self.higherLevel:
                data["contents"] += ["text | " + entry]
        
        data["tags"] = ["spell"] + ["level " + self.level, self.school.lower()]
        for caster in self.casters:
            data["tags"] += [caster.lower()]
        return data

# MAIN PROGRAM #

def main():
    # create empty list
    sourceFolderName = "master_spell"
    itemFileName = "spells-sublist.json"
    itemFolderName = "party"
    useItemFolder = False

    # read commands 
    for index, arg in enumerate(sys.argv):
        print(index, arg)

        # handle source spell folder
        if arg in ["-s", "--source"]:
            sourceFolderName = sys.argv[index + 1]
        elif arg in ["-i", "--item"]:
            itemFileName = sys.argv[index + 1]
        elif arg in ["-f", "--itemfolder"]:
            itemFolderName = sys.argv[index + 1]
            useItemFolder = True
        elif arg in ["-u", "--useitemfolder"]:
            useItemFolder = True
        elif arg in ["-l", "--list"]:
            listKeys(sourceFolderName)
            return

    # print source and item
    print("Source from folder <" + sourceFolderName + ">")
    if useItemFolder:
        print("Items from folder <" + itemFolderName + ">")
        for file in os.listdir("./" + itemFolderName):
            if file.endswith(".json") == False:
                continue
            saveSelectedCards(sourceFolderName, itemFolderName + "/" + file)
    else:
        print("Items from file <" + itemFileName + ">")
        saveSelectedCards(sourceFolderName, itemFileName)

def saveSelectedCards(sourceFolderName, itemFileName):
    cardFileName = re.sub(r"[^\n]*\/([^\/]*).json", r"\1", itemFileName)
    if cardFileName.endswith(".json") == False:
        cardFileName += ".json"
    saveSelectedSpellsAsCard(sourceFolderName, itemFileName, cardFileName)

def readSpellsToGet(itemFileName):
    # read spells to get
    spellsToGet = []
    with open(itemFileName, "r") as myfile:
        data = json.load(myfile)

        for item in data["items"]:
            splitString = item["h"].split("_", 2)
            ss = {}

            ss["name"] = splitString[0].replace("%20", " ").upper()
            ss["source"] = splitString[1].replace("%20", " ").upper()
            ss["found"] = False

            print("searching for " + ss["name"] + " from " + ss["source"])

            spellsToGet += [ss]
    return spellsToGet

def saveSelectedSpellsAsCard(sourceFolderName, itemFileName, cardFileName):
    # get spell json
    spellList = []
    spellsToGet = readSpellsToGet(itemFileName)
    for file in os.listdir("./" + sourceFolderName):
        if file.endswith(".json") == False:
            continue
        print("reading " + file)

        # get spell json
        jsonData = getSpellJsonTool(sourceFolderName + "/" + file, spellsToGet)
        spellList += jsonData

    # save spell json
    os.makedirs("output", exist_ok=True)
    with open("output/" + cardFileName, "w+") as out:
        print("saving " + cardFileName)
        json.dump(spellList, out, indent=4)

    # report missing spells
    for ss in spellsToGet:
        if ss["found"] == False:
            print("unable to find data for " + ss["name"] + " from " + ss["source"])

def listKeys(sourceFolderName):
    keyList = []
    for file in os.listdir("./" + sourceFolderName):
        if file.endswith(".json") == False:
            continue
        print("reading " + file)
        fileName = sourceFolderName + "/" + file
        
        with open(fileName, "r", encoding="utf8") as myfile:
            data = json.load(myfile)

            # get spells from data
            if "spell" in data:
                spells = data["spell"]
                for spell in spells:
                    for key in spell.keys():
                        if key not in keyList:
                            keyList += [key]
            else:
                print("ERROR: no spell data found in " + fileName)
                continue

    for key in keyList:
        print(key)
        





main()