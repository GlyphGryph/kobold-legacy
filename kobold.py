import asyncio
import json
import math
import operator
import os
import random
import re
import shelve
import time
import traceback

import discord
from dotenv import load_dotenv

from src.creature import Creature
from src.dummy_message import DummyMessage
from src.encounter import Encounter
from src.item import Item
from src.kobold import Kobold
from src.party import Party
from src.tile import Tile
from src.tribe import Tribe
from src.world import World


BOT_NAME = 'Lulurnbus#1506'
STATS = ["str", "dex", "con", "int", "wis", "cha"]
STAT_COLOR = {"str": "red", "dex": "white", "con": "black",
              "int": "blue", "wis": "green", "cha": "yellow"}
COLOR_STAT = {"red": "str", "white": "dex", "black": "con",
              "blue": "int", "green": "wis", "yellow": "cha"}
OPP_DIR = {"n": "s", "s": "n", "w": "e", "e": "w"}
OPP_DIR2 = {"n": "s", "s": "n", "w": "e", "e": "w", "u": "d", "d": "u"}
DIR_FULL = {"n": "north", "e": "east", "w": "west", "s": "south"}
GENOME = {"red": [False, False],
          "yellow": [False, False],
          "green": [False, False],
          "blue": [False, False],
          "black": [False, False],
          "white": [False, False]}
ROLENAMES = {"brown": "Mudscale", "red": "Bloodscale", "yellow": "Goldscale", "green": "Jadescale", "blue": "Silkscale",
             "white": "Marblescale", "black": "Coalscale", "orange": "Copperscale", "purple": "Violetscale", "silver": "Silverscale"}
# ADVANCE_TOTALS=[4,8,12,16,20,24]


def get_q_desc(q):
    qs = ["Abysmal", "Awful", "Crude", "Poor", "Normal",
          "Decent", "Good", "Excellent", "Masterwork", "Legendary"]
    q += 4
    if q > 9:
        return "Divine"
    if q < 0:
        return "Broken"
    return qs[q]


def kobold_name():
    vowels = ['a', 'i', 'o', 'u', 'e']
    penvowels = ['a', 'o', 'u', 'ay', 'ee', 'i']
    frontcluster = ['b', 'br', 'bl', 'd', 'dr', 'dl', 'st', 'str', 'stl', 'shl', 'k', 'p',
                    'l', 'lr', 'sh', 'j', 'jr', 'thl', 'g', 'f', 'gl', 'gr', 'fl', 'fr', 'x', 'z', 'zr', 'r']
    cluster = ['b', 'd', 'l', 'f', 'g', 'k', 'p', 'n', 'm', 's', 'v']
    fincluster = ['m', 'r', 'ng', 'b', 'rb', 'mb', 'g', 'lg',
                  'l', 'lb', 'lm', 'rg', 'k', 'rk', 'lk', 'rv', 'v']
    finsyl = ['is', 'us', 'ex1', 'ex2', 'al', 'a', 'ex3']
    first = 1
    syl = random.randint(0, 2)+1
    firstname = ""
    vowel = choice(vowels)
    while syl > 0:
        if syl == 1:
            vowel = choice(penvowels)
        if first == 1 or syl == 1:
            firstname = firstname + choice(frontcluster)
            first = 0
        else:
            firstname = firstname + choice(cluster)
        firstname = firstname + vowel
        syl = syl - 1
    firstname = firstname + choice(fincluster)
    fin = choice(finsyl)
    if vowel in ['o', 'ay', 'u', 'a']:
        if fin == 'ex1':
            fin = choice(['er', 'ar'])
        elif fin == 'ex2':
            fin = choice(['in', 'an'])
        elif fin == 'ex3':
            fin = 'i'
    elif 'ex' in fin:
        fin = choice(['is', 'us', 'al', 'a'])
    firstname = firstname + fin
    return firstname.capitalize()


def tribe_name():
    try:
        f = open('data/tribe_names.txt')
    except:
        console_print('ERROR: Cannot find tribe name list')
        return "Erroneously-named Tribe"
    temp_names = []
    for line in f:
        nam = line.strip('\n')
        nam = nam.capitalize()
        temp_names.append(nam)
    n = choice(temp_names)+" "+choice(temp_names)
    f.close()
    return n

# def alpha_str(str):


def choice(ch):
    if len(ch) == 0:
        return None
    else:
        return random.choice(ch)


def chance(ch):
    if ch <= 0:
        return False
    c = random.randint(1, 100)
    console_print("CHANCE: looking for "+str(ch)+" or less, got "+str(c))
    if c <= abs(ch):
        return True
    else:
        return False


def get_json(fname):
    try:
        f = open(fname)
        stuff = json.load(f)
        f.close()
    except IOError as e:
        console_print('There was a problem loading '+fname+':\n'+e.args[0])
        return None
    except ValueError as e:
        console_print('There was a problem parsing '+fname+':\n'+e.args[0])
        return None
    return stuff


def has_item(self, name, q=1):
    #console_print("has item for "+name)
    if name[0] == "*":
        cat = name.replace("*", "")
    else:
        cat = None
    for i in self.items:
        if (cat and i.name in item_cats[cat]) or (not cat and i.name == name):
            #console_print(i.name+" fits the bill")
            if i.num >= q:
                return i
            else:
                q -= i.num
    return None


def consume_item(self, name, q=1):
    while q > 0:
        i = self.has_item(name)
        qq = q
        q -= i.num
        i.num -= qq
        if i.num <= 0:
            i.destroy("Consumed")


def check_req(self, req, k=None):
    good = "good"
    if k:
        place = k.get_place()
    else:
        place = self
    for q in req:
        if q[0] == "research":
            if isinstance(self, Tribe) and q[1] in self.research:
                #console_print("research req good because in tribe research")
                continue
            #console_print(k.get_name()+" fam with "+q[1]+" = "+str(k.familiar(q[1])))
            if k and k.familiar(q[1]) > 0:
                #console_print("research req good because initiator is familiar")
                continue
            fam = False
            if k:
                for l in k.world.kobold_list:
                    if l.get_place() == place and l.familiar(q[1]) >= 2:
                        fam = True
                        break
            if fam:
                #console_print("research req good because kobold with familiarity here")
                continue
            if place == self:
                good = "Research missing: "+q[1]
            else:
                good = "Unfamiliar research: "+q[1]
        elif q[0] == "item":
            g = "Item missing: "+q[1]
            if place.has_item(q[1]):
                g = "good"
            if k and k.has_item(q[1]):
                g = "good"
            good = g
        elif q[0] == "tool":
            g = "Tool missing: "+q[1]
            for i in place.items:
                if i.tool == q[1]:
                    g = "good"
            if k:
                for i in k.items:
                    if i.tool == q[1]:
                        g = "good"
            if good == "good":
                good = g
        elif q[0] == "building":
            if not isinstance(place, Tribe):
                good = "Can't be done in the overworld."
            elif not place.has_building(q[1]):
                good = "Building missing: "+q[1]
        elif q[0] == "landmark":
            if isinstance(place, Tribe):
                tile = place.world.get_tile(place.x, place.y, place.z)
            else:
                tile = place
            if q[1] not in tile.special:
                good = "Landmark missing: "+q[1]
        elif q[0] == "minlevel":
            if k:
                z = k.z
            else:
                z = self.z
            if q[1] > z:
                good = "Must be done at level "+str(q[1])+" or lower."
        elif q[0] == "maxlevel":
            if k:
                z = k.z
            else:
                z = self.z
            if q[1] < z:
                good = "Must be done at level "+str(q[1])+" or lower."
        elif q[0] == "tribe":
            if isinstance(place, Tribe):
                t = place
            else:
                t = place.get_tribe()
            if t and not q[1]:
                good = "You cannot do that in a tile with a den."
            if not t and q[1]:
                good = "Must be done in a tile with a den."
        elif q[0] == "liquid":
            if isinstance(place, Tribe):
                tile = place.world.get_tile(place.x, place.y, place.z)
            else:
                tile = place
            g = "Liquid source missing: "+q[1]
            for l in tile.special:
                if landmark_data[l].get("liquid_source", "none") == q[1]:
                    g = "good"
            if good == "good":
                good = g
    return good


def get_tri_distance(x1, y1, x2, y2):
    xdist = abs(x1-x2)
    ydist = abs(y1-y2)
    return (min(xdist, ydist)*1.4)+abs(xdist-ydist)


def get_dir(ct, k):
    if abs(ct.x-k.x) > abs(ct.y-k.y):
        if ct.x < k.x:
            return "west"
        elif ct.x > k.x:
            return "east"
    else:
        if ct.y < k.y:
            return "north"
        elif ct.y > k.y:
            return "south"
        else:
            return "same"


def attack_roll(self, target, bonus=0, guarding=False, sparring=False):
    chan = target.get_chan()
    if target.has_trait("protected") and len(target.encounter.creatures) > 1 and chance(75):
        guards = list(target.encounter.creatures)
        if target in guards:
            guards.remove(target)
        ot = target
        target = choice(guards)
        game_print(target.display() +
                   " jumps in the way to protect "+ot.display()+"!", chan)
    game_print(self.display()+" attacks "+target.display()+".", chan)
    adv = 0
    if self.has_trait("greased"):
        if self.save("dex") < 11:
            game_print(self.display() +
                       " slips on the grease and falls prone!", chan)
            return 0
        else:
            game_print(self.display() +
                       " manages to work their way out of the grease.", chan)
            self.del_trait("greased")
    for t in target.traits:
        if trait_data[t].get("target_adv", 0) != 0:
            adv += trait_data[t]["target_adv"]
    for t in self.traits:
        if trait_data[t].get("attack_adv", 0) != 0:
            adv += trait_data[t]["attack_adv"]
    if self.has_trait("oneeye") and self.equip and self.equip.type == "ranged":
        adv -= 1
    if isinstance(self, Kobold) and not self.shaded:
        adv -= 1
    roll = droll(1, 20, adv)
    roll += self.tohit
    if roll >= target.ac or roll == self.tohit+20:  # hits, roll damage
        dmg = self.dmg[2]
        if roll == self.tohit+20 and target.ac-self.tohit < 20:
            game_print("Critical hit!", chan)
            dmg *= 2
        for x in range(self.dmg[0]):
            dmg += random.randint(1, self.dmg[1])
        if self.dmgtype not in ["bludgeoning", "piercing", "slashing"] and self.wearing_nonmage_equipment():
            dmg = math.ceil(dmg/2)
        if guarding and target.save("con") > 13:
            dmg -= random.randint(1, max(1, target.smod("con")+1))
        dmg = max(1, dmg)  # no hitting 0's or negative numbers
        if not sparring:
            target.hp_tax(dmg, "Killed by "+self.display(), self, self.dmgtype)
            if target.has_trait("barrier"):
                reflect = random.randint(0, math.ceil(dmg/4))
                if reflect > 0:
                    self.hp_tax(reflect, "Taste of own medicine",
                                target, "force")
        else:
            if self.equip and self.equip.type == "ranged":
                sk = "marksman"
            elif self.equip and self.equip.type == "magic":
                sk = "sorcery"
            else:
                sk = "melee"
            if chance((dmg-self.skmod(sk))*5):
                self.p("[n] accidentally hits "+target.display() +
                       " with more force than intended!")
                target.hp_tax(random.randint(1, dmg),
                              "Sparring accident", dmgtype=self.dmgtype)
            else:
                self.p("[n] holds back, but would have dealt " +
                       str(dmg)+" damage.")
            target.gain_xp("resilience", dmg*4)
        if self.has_trait("poisoner"):
            if target.save("con") < 11:
                game_print(target.display()+" has been poisoned!", chan)
                target.add_trait("poisoned")
        if self.has_trait("paralyzer"):
            if target.save("con") < 8:
                game_print(target.display()+" has been paralyzed!", chan)
                target.add_trait("paralyzed")
    else:
        game_print("The attack missed.", chan)
        if sparring:
            target.gain_xp("resilience", roll+10)
        dmg = 0
    if dmg > 0:
        if target.has_trait("corroder"):
            if self.equip:
                self.equip.lower_durability(3)
            else:
                self.hp_tax(1, "Acid burn", dmgtype="acid")
    trs = list(self.traits)
    for t in trs:
        if trait_data[t].get("attack_reset", False):
            self.del_trait(t)
    return dmg


def droll(dice, sides, adv=0):
    roll = []
    if adv != 0:
        rolls = 2
    else:
        rolls = 1
    for q in range(rolls):
        r = 0
        for d in range(dice):
            r += random.randint(1, sides)
        roll.append(r)
    if adv == 1:
        return max(roll)
    else:
        return min(roll)


def spawn_item(name, place, num=1, force=False, quality=None):
    i = None
    while num > 0:
        i = Item(name, num)
        if isinstance(place, Kobold) or isinstance(place, Creature):
            bag = False
            if i.inv_size > 0:
                for h in place.items:
                    if h.inv_size > 0:
                        bag = True
            if (bag or len(place.items) >= place.inv_size) and not force:
                place.p("[n]'s inventory is full. Some items were dropped.")
                place = place.get_place()  # inventory full
            elif isinstance(place, Creature) and "haul" not in place.training:
                place.p("[n] doesn't have haul training, so it dropped the item.")
                place = place.get_place()  # inventory full
        num -= i.num
        i.move(place)
        console_print("Spawned: "+name+" x "+str(i.num))
    return i


def make_baby(male, female):
    baby = Kobold(female.tribe)
    baby.age = 0
    if baby in male.world.kobold_list:
        male.world.kobold_list.remove(baby)
    pr = ""
    for g in GENOME:
        if chance(50):
            baby.genome[g][0] = male.genome[g][0]
        else:
            baby.genome[g][0] = male.genome[g][1]
        if chance(50):
            baby.genome[g][1] = female.genome[g][0]
        else:
            baby.genome[g][1] = female.genome[g][1]
        pr += g+":["+str(baby.genome[g][0])+","+str(baby.genome[g][1])+"]; "
    console_print(pr)
    pure = "none"
    purecount = 0
    orange = 0
    purple = 0
    for g in baby.genome:
        if g not in STAT_COLOR.values():
            continue
        if not (baby.genome[g][0] or baby.genome[g][1]):
            console_print("baby has pure "+g+" genomes")
            purecount += 1
            if g in ["red", "white", "black"]:
                orange += 1
            elif g in ["blue", "green", "yellow"]:
                purple += 1
            if pure == "none":
                pure = g
            else:
                pure = "brown"
    if purecount >= 5:
        pure = "silver"
    elif orange > purple+1:
        pure = "orange"
    elif purple > orange+1:
        pure = "purple"
    if pure not in ["none", "brown"]:
        baby.color = pure
    baby.parents = [male.get_name(), female.get_name()]
    return baby


def spell_generic_trait(spell, words, me, target):
    if not target.has_trait(spell["grant_trait"]):
        target.add_trait(spell["grant_trait"])
        return True
    else:
        me.p("That kobold already has " +
             trait_data[spell["grant_trait"]].get("display", spell["grant_trait"])+".")
    return False


def spell_sleep(spell, words, me, target):
    targets = list(target.encounter.creatures)
    spellsave = 6+me.smod("int")+me.skmod("sorcery")
    for t in targets:
        if t.save("wis") < spellsave:
            t.add_trait("sleep")
    target.encounter.pac_check()
    return True


def spell_fireball(spell, words, me, target):
    targets = list(target.encounter.creatures)
    spellsave = 6+me.smod("int")+me.skmod("sorcery")
    dmg = spell["dmg"][2]
    for x in range(spell["dmg"][0]):
        dmg += random.randint(1, spell["dmg"][1])
    if me.wearing_nonmage_equipment():
        dmg = math.ceil(dmg/2)
    for t in targets:
        bdmg = dmg
        if t.save("dex") >= spellsave:
            bdmg = math.floor(dmg/2)
        t.hp_tax(bdmg, spell["name"], me, "fire")
    return True


def spell_tremor(spell, words, me, target):
    targets = list(target.encounter.creatures)
    spellsave = 6+me.smod("int")+me.skmod("sorcery")
    dmg = spell["dmg"][2]
    for x in range(spell["dmg"][0]):
        dmg += random.randint(1, spell["dmg"][1])
    p = me.get_place()
    if p.z == 0 and not me.dungeon:
        dmg = math.ceil(dmg/2)
    else:
        p.stability -= 5
        p.cave_in(party.owner)
    if me.wearing_nonmage_equipment():
        dmg = math.ceil(dmg/2)
    for t in targets:
        bdmg = dmg
        if t.save("dex") >= spellsave:
            bdmg = math.floor(dmg/2)
        t.hp_tax(bdmg, spell["name"], me, "bludgeoning")
    return True


def spell_freeze(spell, words, me, t):
    spellsave = 6+me.smod("int")+me.skmod("sorcery")
    dmg = spell["dmg"][2]
    for x in range(spell["dmg"][0]):
        dmg += random.randint(1, spell["dmg"][1])
    if me.wearing_nonmage_equipment():
        dmg = math.ceil(dmg/2)
    if t.save("con") >= spellsave:
        dmg = math.floor(dmg/2)
    else:
        t.add_trait("frozen")
    t.hp_tax(dmg, spell["name"], me, "cold")
    return True


def spell_grease(spell, words, me, t):
    spellsave = 4+me.smod("int")+me.skmod("sorcery")
    for c in t.encounter.creatures:
        if c.save("dex") >= spellsave:
            me.p(c.display()+" was unaffected.")
        else:
            me.p(c.display()+" is greased!")
            c.add_trait("greased")
    return True


def spell_sparkle(spell, words, me, t):
    spellsave = 6+me.smod("int")+me.skmod("sorcery")
    if t.save("dex") >= spellsave:
        me.p(t.display()+" was unaffected.")
    else:
        me.p(t.display()+" is blinded!")
        t.add_trait("blinded")
    return True


def spell_charm(spell, words, me, t):
    if t.tribe:
        me.p("You can only cast that on a tribeless kobold.")
        return False
    spellsave = 6+me.smod("int")+me.skmod("sorcery")
    if t.save("cha") >= spellsave:
        me.p(t.display()+" was unaffected.")
    else:
        me.p(t.display()+" is charmed!")
        t.add_trait("charmed")
    return True


def spell_missile(spell, words, me, t):
    dmg = spell["dmg"][2]
    for x in range(spell["dmg"][0]):
        dmg += random.randint(1, spell["dmg"][1])
    if me.wearing_nonmage_equipment():
        dmg = math.ceil(dmg/2)
    t.hp_tax(dmg, spell["name"], me, "force")
    return True


def spell_lifesteal(spell, words, me, t):
    me.tohit = me.smod("int")+math.floor(me.skmod("sorcery")/2)
    me.dmg = list(spell["dmg"])
    me.dmgtype = spell["dmgtype"]
    dmg = attack_roll(me, t)
    if dmg > 0:
        me.hp_gain(math.ceil(dmg/2))
    return True


def spell_generic_attack(spell, words, me, t):
    me.tohit = me.smod("int")+math.floor(me.skmod("sorcery")/2)
    me.dmg = list(spell["dmg"])
    me.dmgtype = spell["dmgtype"]
    attack_roll(me, t)
    return True


def spell_scout(spell, words, k, target):
    if len(words) > 2 and words[2][0] in DIR_FULL:
        d = words[2][0]
    else:
        k.p("That is not a valid direction.")
        return False
    k.p("[n] sees a vision from the "+DIR_FULL[d]+"...")
    p = k.get_place()
    if isinstance(p, Tribe):
        tile = k.world.get_tile(k.x, k.y, k.z)
    else:
        tile = p
    place = tile.get_border(d)
    if k.party:
        for e in k.world.encounters:
            if e.place == place:
                e.examine(k)
    place.examine(k)
    return True


def spell_brace(spell, words, k, target):
    if k.z == 0 and not k.dungeon:
        k.p("There's no point in casting this on the surface.")
        return False
    s = k.spell_strength(spell)
    p = k.get_place()
    if isinstance(p, Tribe):
        p = k.world.get_tile(k.x, k.y, k.z)
    p.stability += s
    k.p("The cavern's stability increases.")
    return True


def spell_prospect(spell, words, k, target):
    if len(words) < 3:
        k.p("Please specify a mineral to prospect for.")
        return False
    if k.z == 0 and not k.dungeon:
        k.p("There is nothing to prospect for on this level.")
        return False
    mineral = None
    for i in item_data:
        if i.get("minelevel", 0) > 0 and words[2].lower() in i["name"].lower():
            mineral = i["name"]
            break
    if not mineral:
        k.p("No such mineral '"+words[2]+"'.")
        return False
    ct = k.world.find_tile_feature(10, k, mineral, "resources", gen=True)
    if ct:
        dir = "none"
        if abs(ct.x-k.x) > abs(ct.y-k.y):
            if ct.x < k.x:
                dir = "to the west."
            elif ct.x > k.x:
                dir = "to the east."
        else:
            if ct.y < k.y:
                dir = "to the north."
            elif ct.y > k.y:
                dir = "to the south."
            else:
                dir = "right under their nose."
        k.p("[n] senses a node of "+mineral+" "+dir)
    else:
        k.p("[n] doesn't sense any "+mineral+" nearby.")
    return True


def spell_wellness(spell, words, me, target):
    for t in target.traits:
        if trait_data[t].get("heal_save_to_cure", False):
            me.p(target.display()+" has been cured of their " +
                 trait_data[t].get("display", t)+" condition!")
            target.del_trait(t)
            break
    return True


def spell_regen(spell, words, me, target):
    s = me.spell_strength(spell)
    for t in target.traits:
        if trait_data[t].get("regenerate", False):
            s -= 5
            me.p(target.display()+"'s lost flesh is restored!")
            target.del_trait(t)
            break
    target.hp_gain(max(1, s))
    return True


def spell_heal(spell, words, me, target):
    s = me.spell_strength(spell)
    target.hp_gain(s)
    return True


def spell_energy(spell, words, me, target):
    s = spell["strength"]
    if target.has_trait("overworked"):
        target.p(
            "[n] has already been energized today. Any more and their body might give out...")
        return False
    else:
        target.ap_gain(s)
        target.add_trait("overworked")
    return True


def spell_transfusion(spell, words, me, target):
    blood = False
    for i in me.items:
        if i.liquid and "Blood" in i.liquid and i.liquid_units > 0:
            blood = True
            i.liquid_units -= 1
    if not blood and me.hp <= 1:
        me.p("You have no life to give right now.")
        return False
    s = min(5, me.hp-1, target.max_hp-target.hp)
    if s > 0:
        if not blood:
            me.hp_tax(s, "Gave their life away", dmgtype="arcane")
        target.hp_gain(s)
        return True
    else:
        me.p("That won't have any effect.")
        return False


def spell_soulbind(spell, words, me, target):
    if len(words) == 2:
        if me.bound and me.bound.bound == me:
            if me.mp_tax(2):
                me.bound.move(me)
                me.p("[n] holds out their hand, and green light converges within it forming the shape of a " +
                     me.bound.display()+". The green light fades, and the item remains in their grasp.")
        else:
            me.p(
                "Nothing happens. [n] must not have a soulbound item in this plane of existence...")
    else:
        target = find_item(words[2], me)
        if target:
            if target.stack > 1 or target.type == "corpse":
                me.p("Can't soulbind the "+target.display()+".")
            elif target.bound:
                me.p(target.display()+" is already bound to " +
                     target.bound.display()+"'s soul.")
            elif me.mp_tax(10):
                target.bound = me
                me.bound = target
                me.p("The "+target.display() +
                     " glows a soft green in [n]'s hands and then fades. [n] feels it as though it is a part of themselves.")
                return True
        else:
            me.p("Target '"+words[2]+"' not found.")
    return False


def spell_rupture(spell, words, me, target):
    me.tohit = me.smod("int")+math.floor(me.skmod("sorcery")/2)
    me.dmg = list(spell["dmg"])
    me.dmgtype = spell["dmgtype"]
    dmg = attack_roll(me, target)
    if dmg > 0:
        if isinstance(target, Kobold):
            liq = "Kobold Blood"
        else:
            liq = "Blood"
        for i in me.items:
            if i.liquid_capacity > i.liquid_units and (i.liquid is None or i.liquid == liq):
                target.liquid = liq
                target.liquid_units += 1
                me.p("The "+target.display()+" fills with "+liq+".")
                break
    return True


def spell_condensate(spell, words, me, target):
    if target.liquid_capacity > target.liquid_units and (target.liquid is None or target.liquid == "Water"):
        target.liquid = "Water"
        target.liquid_units += 1
        me.p("The "+target.display()+" fills with water.")
        return True
    else:
        me.p("Target must be a container that can hold 1 additional unit of water.")
    return False


def spell_dislocate(spell, words, me, target):
    if me.z > 0 and not me.dungeon:
        p = me.world.get_tile(me.x, me.y, me.z)
        d = words[2][0].lower()
        if d not in list(DIR_FULL.keys()):
            me.p("Invalid direction '"+words[2]+"'")
            return False
        if p.mined[d] >= 0 and p.resources[d]:
            res = p.resources[d]
        else:
            res = "Stone Chunk"
        n = 1
        for z in item_data:
            if z["name"] == res:
                n = random.randint(1, z.get("stack", 1))
        m = spawn_item(res, me.get_place(), n)
        me.p(m.display()+" manifests on the ground.")
        p.mined[d] += m.veinsize
        if p.mined[d] == 0 and p.resources[d]:
            k.p("[n] has revealed a node of "+p.resources[d]+"!")
        elif res != "Stone Chunk" and chance(p.mined[d]*5):
            k.p("The "+res+" vein is depleted.")
            p.resources[d] = None
        p.stability -= 5
        p.cave_in(me, d)
        return True
    else:
        me.p("There's nothing to dislocate here.")
    return False


def spell_enchant(spell, words, me, target):
    s = max(1, me.spell_strength(spell))+3
    if target.quality < s:
        target.quality += 1
    else:
        me.p("[n]'s Sorcery isn't strong enough to increase the quality any further.")
        return False
    me.p("[n]'s magic has enhanced the "+target.display() +
         " to "+get_q_desc(target.quality)+" quality.")
    return True


def spell_hotfix(spell, words, me, target):
    if target.durability > 0:
        target.durability = target.max_durability
        target.dura_loss += 1
        me.p("[n] performs a quick and dirty fix on the "+target.display() +
             ", making it like new - but abusing the item in the process.")
        return True
    else:
        me.p("That cannot be hotfixed.")
        return False


def spell_mending(spell, words, me, target):
    if target.durability > 0:
        s = me.spell_strength(spell)
        target.durability += s
        if target.durability > target.max_durability:
            target.durability = target.max_durability
        me.p("[n] fixes the wear and tear in the "+target.display() +
             ", adding "+str(s)+" points of durability.")
        return True
    else:
        me.p("That cannot be mended.")
        return False


def spell_goodberry(spell, words, me, target):
    s = max(me.spell_strength(spell), 1)
    me.p(str(s)+" Goodberries materialize in the palm of [n]'s hand.")
    spawn_item("Goodberry", me, s)
    return True


def spell_blade(spell, words, me, target):
    me.p("A blade of magical force materializes in [n]'s hands.")
    spawn_item("Spectral Blade", me)
    return True


def spell_arrow(spell, words, me, target):
    me.p("A bow and arrows of magical force materialize in [n]'s hands.")
    spawn_item("Spectral Bow", me)
    spawn_item("Spectral Arrow", me, 20)
    return True


def spell_bloodscry(spell, words, me, target):
    target.hp_tax(1, "Blood sampled", me, dmgtype="arcane")
    genes = []
    for g in target.genome:
        text = g+": "
        for x in range(2):
            if target.genome[g][x]:
                text += g[0].capitalize()
            else:
                text += g[0].lower()
        genes.append(text)
    target.p("[n] feels a jolt of pain as their blood is extracted and scattered through the air. " +
             me.display()+" interprets the patterns it makes...\n[n]'s genomes: "+"; ".join(genes))
    return True


def spell_ageup(spell, words, me, target):
    if target.age < 6:
        target.age_up()
    target.age += 1
    target.p("[n] rapidly ages. It's disorienting, but they feel more mature now.")
    return True


def spell_color(spell, words, me, target):
    oldcolor = target.color
    if len(words) > 3:
        gems = {"red": "Ruby", "yellow": "Topaz", "green": "Emerald",
                "blue": "Sapphire", "white": "Opal", "black": "Onyx", "brown": "Quartz"}
        c = words[3].lower()
        if c in gems:
            if target.color != c:
                if me.has_item(gems[c], 5):
                    me.consume_item(gems[c], 5)
                    me.p("[n] arranges the "+gems[c] +
                         " gems in a pentagram around "+target.display()+".")
                    target.color = c
                else:
                    me.p("You need 5 " +
                         gems[c]+" gems to change the target to that color.")
                    return False
            else:
                me.p(target.display()+" is already "+c+".")
                return False
        else:
            me.p("Invalid color '"+words[3]+"'.")
            return False
    else:
        colors = list(ROLENAMES.keys())
        if target.color in colors:
            colors.remove(target.color)
        target.color = choice(colors)
    if target.color != "brown":
        target.genome[target.color] = [False, False]
    if oldcolor != "brown":
        if chance(50):
            target.genome[oldcolor][0] = True
        else:
            target.genome[oldcolor][1] = True
    else:
        for g in target.genome:
            if g in COLOR_STAT and g != target.color and (not target.genome[g][0] and not target.genome[g][1]):
                if chance(50):
                    target.genome[g][0] = True
                else:
                    target.genome[g][1] = True
    action_queue.append(["delrole", ROLENAMES[oldcolor], target.d_user_id])
    action_queue.append(["addrole", ROLENAMES[target.color], target.d_user_id])
    target.p("[n]'s scales change color before their eyes.")
    return True


def spell_sexchange(spell, words, me, target):
    if len(target.eggs) == 0:
        if target.has_trait("nonbinary"):
            me.p("This won't have any effect; " +
                 target.display()+" is non-binary.")
            return False
        else:
            if target.male:
                target.male = False
            else:
                target.male = True
            target.p("[n] feels a bit strange...")
            return True
    else:
        me.p("Can't cast this on a pregnant kobold.")
        return False


def spell_message(spell, words, me, target):
    if len(words) < 4:
        me.p("Please enter a message.")
        return False
    if len(words[3]) > 250:
        me.p("Your message must be 250 characters or less.")
        return False
    target = find_kobold(words[2], w=me.world)
    if target:
        me.p("[n] sends a message to "+target.display()+": \""+words[3]+"\"")
        if target.nick:
            target.p("<@!"+str(target.d_user_id) +
                     "> receives a telepathic message from "+me.display()+": \""+words[3]+"\"")
        else:
            target.p("[n] receives a telepathic message from " +
                     me.display()+": \""+words[3]+"\"")
        return True
    else:
        me.p("Can't find a kobold in the world by that name.")
        return False


def spell_recall(spell, words, me, target):
    if not me.tribe:
        me.p("You do not have a home den to recall to.")
        return False
    elif me.get_place() == me.tribe:
        me.p("You are already in your den.")
        return False
    cost = len(me.party.members)
    if me.mp_tax(cost):
        for k in me.party.members:
            k.dungeon = None
        me.party.move(me.tribe.x, me.tribe.y, me.tribe.z, 0)
        me.gain_xp("sorcery", cost*5)
        for e in me.world.encounters:
            if me.party in e.engaged:
                e.disengage(me.party)
        return True
    else:
        return False


async def cmd_cast(words, me, chan):
    sp = None
    for s in me.spells:
        if words[1].lower() in s.lower():
            sp = find_spell(s)
            if sp:
                break
    if not sp:
        me.p("[n] doesn't know that spell.")
        return False
    cost = sp.get("cost", 0)
    if cost > me.mp:
        me.p("[n] doesn't have enough MP to cast that. (need " +
             str(sp["cost"])+", have "+str(me.mp)+")")
        return False
    args = " ".join(words).split(" ", sp.get("args", 2))
    if len(args) < sp.get("args", 2)+1-sp.get("args_optional", 0):
        me.p("Spell usage:\n"+sp["desc"])
        return False
    target = None
    targ = sp.get("target", None)
    if targ == "kobold" or targ == "living":
        if args[sp.get("targ_arg", len(args)-1)].lower() in ["self", "me", "myself"]:
            target = me
        else:
            target = find_kobold(
                args[sp.get("targ_arg", len(args)-1)].lower(), me.get_place(), me.world)
        if not target and targ == "living":
            target = find_creature_i(
                args[sp.get("targ_arg", len(args)-1)].lower(), me)
        if not target:
            if targ == "living":
                me.p("Kobold/creature '" +
                     words[sp.get("targ_arg", len(words)-1)]+"' not found.")
            else:
                me.p("Kobold '" +
                     words[sp.get("targ_arg", len(words)-1)]+"' not found.")
            return False
        if target == me and not sp.get("can_target_self", False):
            me.p("Cannot target self with that spell.")
            return False
        if isinstance(target, Kobold) and me != target and target.nick and sp.get("require_consent", False):
            ch = discord.utils.get(guild.channels, name=target.get_chan())
            await ch.send("<@!"+str(target.d_user_id)+"> A moment of your time please...")
            if not await confirm_prompt(ch, me.display()+" wants to cast "+sp["name"]+" with you as the target. Your consent is required. Do you accept?", discord.utils.get(guild.members, id=target.d_user_id)):
                me.p("Action aborted; consent not given.")
                return False
    if targ == "item":
        target = await multi_select(chan, args[sp.get("targ_arg", len(args)-1)].lower(), me, sp.get("start_in_inv", True), sp.get("place", "any"), sp.get("target_type", None))
        if not target:
            return False
    if targ == "enemy" or targ == "enemy_all":
        engage = None
        for e in me.world.encounters:
            if me.party and me.party in e.engaged:
                if me.didturn:
                    me.p(
                        me.display()+" has already used their action for this combat round.")
                    return
                engage = e
                break
        if engage:
            if not sp.get("combat", True):
                me.p("That spell cannot be cast in combat.")
                return False
            if len(engage.creatures) == 1 or targ == "enemy_all":
                target = engage.creatures[0]
            else:
                for c in engage.creatures:
                    if args[sp.get("targ_arg", len(args)-1)].lower() == c.name[-1].lower():
                        target = c
            if not target:
                me.p("Use the letter corresponding to the target you want. (A, B, C)")
                return False
        else:
            me.p("That spell can only be cast in combat.")
            return False
    me.p("[n] casts "+sp["name"]+".")
    done = globals()[sp.get("function", "sorry nothing")](sp, args, me, target)
    if done and cost > 0:
        me.mp_tax(cost)
        me.gain_xp("sorcery", cost*5)
        return True


async def cmd_graveyard(words, me, chan):
    embeds = []
    amount = 0
    msg = ""
    for g in me.tribe.graveyard:
        msg += g+" - "+me.tribe.graveyard[g]+"\n"
        if amount % 10 == 9:
            embeds.append(discord.Embed(
                type="rich", title="Graveyard", description=msg))
            msg = ""
        amount += 1
    embeds.append(discord.Embed(
        type="rich", title="Graveyard", description=msg))
    c = 1
    for e in embeds:
        e.set_footer(text="Showing graves "+str(c)+"-" +
                     str(min(c+9, amount))+" of "+str(amount)+". React to scroll.")
        c += 10
    await embed_group(chan, embeds)
    return True


async def cmd_crafts(words, me, chan):
    amount = 0
    embeds = []
    msg = ""
    for c in craft_data:
        if len(words) > 1 and words[1].lower() not in c["result"].lower():
            continue
        good = check_req(me.tribe, c.get("req", []), me)
        if good == "good":
            mats = []
            for m in c["materials"]:
                mats.append(m)
            msg += "\n"+c["result"]+": "
            if c.get("mana", 0) > 0:
                msg += str(c["mana"])+" Mana."
            else:
                msg += str(c["work"])+" AP."
            msg += " Skill: "+c.get("skill", "crafting") + \
                ". Materials: "+", ".join(mats)
            if amount % 10 == 9:
                embeds.append(discord.Embed(
                    type="rich", title="Available crafts", description=msg))
                msg = ""
            amount += 1
    embeds.append(discord.Embed(
        type="rich", title="Available crafts", description=msg))
    c = 1
    for e in embeds:
        e.set_footer(text="Showing results "+str(c)+"-" +
                     str(min(c+9, amount))+" of "+str(amount)+". React to scroll.")
        c += 10
    await embed_group(chan, embeds)
    return True


async def cmd_researches(words, me, chan):
    ar = me.tribe.get_available_research()
    msg = ""
    amount = 0
    embeds = []
    for res in ar:
        r = find_research(res)
        diff = r["diff"]
        if r.get("repeatable", False):
            diff += int((me.tribe.research.count(res)**1.5)*r["diff"])
        msg += "\n\n" + \
            r["name"]+" ("+str(me.tribe.research_prog.get(r["name"], 0)
                               )+"/"+str(diff)+") - "+r["desc"]
        if amount % 5 == 4:
            embeds.append(discord.Embed(
                type="rich", title="Available research projects", description=msg))
            msg = ""
        amount += 1
    if msg != "":
        embeds.append(discord.Embed(
            type="rich", title="Available research projects", description=msg))
    c = 1
    for e in embeds:
        e.set_footer(text="Showing results "+str(c)+"-" +
                     str(min(c+4, amount))+" of "+str(amount)+". React to scroll.")
        c += 5
    if len(embeds) > 0:
        await embed_group(chan, embeds)
    else:
        await chan.send("No research projects available at this time.")
    return True


async def cmd_buildings(words, me, chan):
    if not me.tribe:
        me.p("You can't build things if you aren't in a tribe (for now)")
        return False
    p = me.get_place()
    tile = me.world.get_tile(me.x, me.y, me.z)
    if isinstance(p, Tribe):
        intribe = True
    else:
        intribe = False
    ar = []
    for r in building_data:
        good = True
        if not r.get("landmark", False) and not intribe:
            continue
        if intribe and r["name"] in p.buildings and not r.get("repeatable", False):
            good = False
        if r.get("landmark", False) and r["name"] in tile.special and not r.get("repeatable", False):
            good = False
        if good:
            if intribe:
                g = check_req(p, r.get("req", []), me)
            else:
                g = check_req(None, r.get("req", []), me)
            if g != "good":
                good = False
        if good:
            ar.append(r)
    msg = ""
    amount = 0
    embeds = []
    for r in ar:
        if intribe and r.get("landmark", False):
            loc = tile
        else:
            loc = p
        msg += "\n\n" + \
            r["name"]+" ("+str(loc.building_prog.get(r["name"], 0)
                               )+"/"+str(r["work"])+") - "+r["desc"]
        if len(r.get("materials", [])) > 0:
            msg += "\nMaterials: "+", ".join(r["materials"])
        else:
            msg += "\nMaterials: None"
        if amount % 5 == 4:
            embeds.append(discord.Embed(
                type="rich", title="Available building projects", description=msg))
            msg = ""
        amount += 1
    if msg != "":
        embeds.append(discord.Embed(
            type="rich", title="Available building projects", description=msg))
    c = 1
    for e in embeds:
        e.set_footer(text="Showing results "+str(c)+"-" +
                     str(min(c+4, amount))+" of "+str(amount)+". React to scroll.")
        c += 5
    if len(embeds) > 0:
        await embed_group(chan, embeds)
    else:
        await chan.send("No building projects available at this time.")
    return True


def cmd_farming(words, me, target):
    farms = {}
    p = me.get_place()
    if isinstance(p, Tribe):
        p = me.world.get_tile(p.x, p.y, p.z)
    msg = "Farm operational: "
    gotfarm = False
    for b in p.special:
        if " Farm" in b:
            msg += b
            gotfarm = True
    if not gotfarm:
        msg += "None\n\nYou'll have to build a farm before you can grow anything here."
    else:
        msg += "\nCapacity: "+str(p.farm_cap)+"/1000"
        fs = []
        for f in farms:
            fs.append(f+" x"+str(farms[f]))
        msg += ", ".join(fs)+"\n\nCrop progress:"
        for f in p.farming_prog:
            msg += "\n"+f+": "+str(p.farming_prog[f])+" (Yield: "
            for i in item_data:
                if i["name"] == f:
                    msg += str(math.floor(p.farming_prog[f] /
                               i["farming"]["prog"]))+")"
    if me.tribe:
        msg += "\n\nDomesticated: " + \
            ", ".join(me.tribe.farmable)+"\nIn Progress:"
        for f in me.tribe.dom_prog:
            if f in me.tribe.farmable:
                continue
            msg += "\n"+f+": "
            for i in item_data:
                if i["name"] == f:
                    msg += str(me.tribe.dom_prog[f]) + \
                        "/"+str(i["farming"]["diff"])
    else:
        msg += "\n\nYou are not in a tribe, so you don't have access to a seed cache and cannot domesticate anything."
    action_queue.append(["embed", me.get_chan(), discord.Embed(
        type="rich", title="Farming Info", description=msg)])
    return True


def cmd_cpgive(words, me, target):
    if not target.nick:
        me.p("Must target a named kobold.")
        return False
    if len(words) > 1:
        try:
            am = int(words[2])
        except:
            am = 0
        if am <= 0:
            me.p("Please enter a positive number.")
            return False
    else:
        am = 999
    if am > me.cp:
        me.p("You don't have that much CP to give.")
        return False
    am = min(target.max_cp-target.cp, am)
    if am == 0:
        me.p("The target can't hold any more CP.")
        return False
    target.cp += am
    me.cp -= am
    me.p("[n] gives "+str(am)+" CP to "+target.display()+".")
    return True


def cmd_kennel(words, me, chan):
    p = me.get_place()
    if isinstance(p, Tribe):
        cl = p.kennel
        cln = "Kennel"
    else:
        cl = p.pasture
        cln = "Pasture"
    kl = []
    for k in cl:
        kl.append(k.display()+" - "+str(k.hp)+"/"+str(k.max_hp) +
                  " HP - Training: "+", ".join(k.training))
    e = discord.Embed(type="rich", title=cln, description="\n".join(kl))
    action_queue.append(["embed", me.get_chan(), e])
    return True


async def cmd_kobolds(words, me, chan):
    embeds = []
    pages = ["resources", "status", "stats", "skills",
             "items", "votes", "community effort"]
    if len(words) > 1:
        start = None
        for p in pages:
            if words[1].lower() in p:
                start = p
        if not start:
            me.p("Invalid page '"+words[1]+"'.")
            return False
        pages.remove(start)
        pages.insert(0, start)
    bolds = []
    for k in me.world.kobold_list:
        if k.get_place() == me.get_place():
            bolds.append(k)
    for p in pages:
        l = []
        pdesc = ""
        pgn = 1
        for k in bolds:
            if p == "resources":
                m = k.display()+" - "+str(k.hp)+"/"+str(k.max_hp) + \
                    " HP, "+str(k.ap)+"/"+str(k.max_ap)+" AP, "
                if k.max_mp > 0:
                    m += str(k.mp)+"/"+str(k.max_mp)+" Mana, "
                if k.nick:
                    m += str(k.cp)+"/"+str(k.max_cp)+" CP, "
                m += "Status: "
                st = []
                for t in k.traits:
                    if trait_data[t].get("high", False):
                        st.append(trait_data[t]["display"])
                if len(st) > 0:
                    m += ", ".join(st)
                else:
                    m += "Fine"
                l.append(m)
            elif p == "status":
                m = k.display()+" - "
                st = []
                for t in k.traits:
                    if trait_data[t].get("visible", False):
                        st.append(trait_data[t]["display"])
                if len(st) > 0:
                    m += ", ".join(st)
                else:
                    m += "Fine"
                l.append(m)
            elif p == "skills":
                sk = []
                for s in skill_data:
                    ski = k.skmod(s)
                    if ski != k.skill[s]:
                        sk.append("[**"+skill_data[s]["icon"]+str(ski)+"**]")
                    elif k.skill[s] > 0:
                        sk.append(
                            "["+skill_data[s]["icon"]+str(k.skill[s])+"]")
                l.append(k.display()+" - "+" ".join(sk))
            elif p == "items":
                n = []
                if k.carry:
                    n.append(k.carry.display())
                for i in k.items:
                    n.append(i.display())
                m = k.display()+"("+str(len(k.items))+"/"+str(k.inv_size)+") - "+", ".join(n)
                l.append(m)
            elif p == "votes":
                if k.age < 6:
                    vote = "Too young"
                else:
                    vote = "Abstain"
                    for j in me.world.kobold_list:
                        if not k.nick:
                            k.vote = -1
                        if k.vote == j.id:
                            vote = "Voting for "+j.display()
                l.append(k.display()+" - "+vote)
            elif p == "community effort":
                if k.ce == "":
                    vote = "No preference"
                else:
                    vote = k.ce
                l.append(k.display()+" - "+vote)
            else:
                l.append(k.display()+" "+str(k.s))
            if len("\n".join(l)) > 4000:
                ll = l.pop()
                pdesc = " pg "+str(pgn)
                pgn += 1
                e = discord.Embed(
                    type="rich", title="Kobolds here ("+p+pdesc+")", description="\n".join(l))
                embeds.append(e)
                e.set_footer(text="React to see different information.")
                l = [ll]
                pdesc = " pg "+str(pgn)
        e = discord.Embed(type="rich", title="Kobolds here (" +
                          p+pdesc+")", description="\n".join(l))
        embeds.append(e)
        e.set_footer(text="React to see different information.")
    await embed_group(chan, embeds)
    return True


def cmd_epitaph(words, k, target):
    if len(words[2]) > 250:
        k.p("Only about 250 characters will fit on a gravestone.")
        return False
    for g in k.tribe.graveyard:
        if words[1].lower() in g.lower():
            if k.tribe.graveyard[g] != "Nothing written":
                k.p("Something else was already written here.")
                return False
            k.tribe.graveyard[g] = words[2]
            k.p("[n] has written an epitaph for "+g+":\n"+words[2])
            return True
    k.p("Kobold not found. Must be a kobold who was buried in this graveyard.")
    return False


def cmd_bury(words, k, target):
    if target.name == "Kobold Corpse" or target.name == "Kobold Skeleton":
        target.destroy("Buried")
        for f in ["Goblin", "Human", "Elf", "Dwarf"]:
            if f not in k.tribe.heat_faction:
                continue
            k.tribe.heat_faction[f] -= 1
        k.p("[n] buries the corpse of "+target.owner +
            ". They will never be forgotten here.")
        k.tribe.graveyard[target.owner] = "Nothing written"
        return True
    else:
        k.p("Must be a kobold corpse or skeleton.")
    return False


def cmd_rescues(words, k, target):
    if k.has_trait("rescues"):
        k.del_trait("rescues")
        k.p("[n] is no longer looking for rescues.")
    else:
        k.add_trait("rescues")
        k.p("[n] is willing to be rescued.")
    return True


def cmd_orders(words, k, target):
    if k.orders:
        k.orders = False
        k.p("[n] will no longer take orders from the Overseer.")
    else:
        k.orders = True
        k.p("[n] will now follow the Overseer's orders.")
    return True


def cmd_fast(words, k, target):
    if k.has_trait("fed"):
        k.p("[n] has already eaten so this will not have any effect.")
        return False
    if k.has_trait("fasting"):
        k.del_trait("fasting")
        k.p("[n] is no longer fasting this month.")
    else:
        k.add_trait("fasting")
        k.p("[n] is fasting this month and will not automatically eat anything.")
    return True


def cmd_rest(words, k, target):
    if k.has_trait("resting"):
        k.del_trait("resting")
        k.p("[n] is no longer resting this month.")
    else:
        k.add_trait("resting")
        k.p("[n] is resting this month and will not participate in tasks.")
    return True


async def cmd_pacify(words, k, target):
    if target.encounter.pacified:
        k.p(target.display()+" will not play this game with you.")
        return False
    elif not isinstance(target, Kobold) and target.language == "none":
        if target.stats["int"] < 6 and target.companion:
            bait = await multi_select(discord.utils.get(guild.channels, name=k.get_chan()), "", k, place="inv", type="bait/food/material")
            good = False
            if bait:
                for b in target.diet:
                    cat = b.replace("*", "")
                    if cat == bait.name or (cat in item_cats and bait.name in item_cats[cat]):
                        good = True
            if bait and good:
                k.p("[n] throws the "+bait.name +
                    " on the floor in front of "+target.display()+".")
                bait.num -= 1
                if bait.num <= 0:
                    bait.destroy("Bait")
                rpower = k.smod("cha")+(k.skmod("animals")*2)
                roll = rpower+random.randint(1, 20)
                diff = 6+target.stats["int"] + \
                    (target.cr*2)+len(target.encounter.creatures)
                console_print((roll, diff))
                if roll > diff:
                    k.p(target.display()+" starts eating the " +
                        bait.name+". It seems to be satisfied.")
                    target.add_trait("pacified")
                    target.encounter.pac_check()
                    exp = diff
                else:
                    k.p(target.display()+" ignores the "+bait.name+".")
                    exp = roll
                k.gain_xp("animals", max(0, exp)+5)
                return True
            else:
                k.p("You don't have anything " +
                    target.display()+" would be interested in.")
        else:
            k.p("You can't pacify "+target.display()+".")
    else:
        if not isinstance(target, Kobold):
            good = check_req(
                None, [["research", target.language+" Language"]], k)
            if good != "good":
                k.p("Can't pacify "+target.display()+". "+good)
                return False
            diff = 5+target.stats["cha"]+len(target.encounter.creatures)
        else:
            diff = target.s["cha"]+len(target.encounter.creatures)
        k.p("[n] appeals to "+target.display() +
            " and tries to get them to back down.")
        roll = droll(1, 20)+k.smod("cha")+k.skmod("negotiation")
        if k.tribe and not isinstance(target, Kobold) and target.faction in k.tribe.heat_faction:
            diff += math.ceil(k.tribe.heat_faction[target.faction]/20)
        if roll >= diff:
            k.p(target.display() +
                " agrees and decides to leave [n]'s party alone.")
            target.encounter.disengage_all()
            target.encounter.hostile = False
            target.encounter.pacified = True
            exp = diff
        else:
            k.p("[n]'s words fail to reach "+target.display()+".")
            exp = roll
        k.gain_xp("negotiation", exp)
        return True
    return False


def cmd_negotiate(words, k, target):
    p = k.get_place()
    f = None
    if isinstance(p, Tile):
        for l in p.special:
            if landmark_data[l].get("faction", None):
                f = landmark_data[l]["faction"]
                break
    if f not in k.tribe.shc_faction:
        k.tribe.shc_faction[f] = 0
    if not f:
        k.p("There is no faction base here.")
    elif not k.tribe:
        k.p("There's no point to this, you are rogue...")
    elif k.tribe.shc_faction[f] < 1:
        k.p("The "+f+" faction has already called a truce.")
    elif k.has_trait("goblin_talks"):
        k.p("[n] has already tried to negotiate this month. They won't hear you again for a while.")
    else:
        n = k.party.best_trader()
        bossnametable = {"Goblin": "Goblin Boss", "Human": "Human Lord",
                         "Elf": "Elf Princess", "Dwarf": "Dwarf Foreman", "Gnoll": "Gnoll Chieftain"}
        if f in bossnametable:
            bn = bossnametable[f]
        else:
            k.p("Cannot negotiate with this faction: they are not interested in peace!")
            return False
        if f == "Goblin":
            lang = "Goblin Language"
        elif f == "Gnoll":
            lang = "Gnoll Language"
        else:
            lang = "Common Language"
        if check_req(p, [["research", lang]], k) != "good":
            k.p("Cannot negotiate with this faction: you lack familiarity with "+lang+".")
            return False
        k.p("[n] offers a greeting in the "+f+" tongue and asks for a meeting. The " +
            bn+" invites the party to sit with them and the peace talks begin...")
        roll = droll(1, 20)+n[1]
        diff = math.ceil(math.sqrt(k.tribe.heat_faction[f]))+5
        if roll < diff:
            k.p("The talks didn't go so well. The "+bn +
                " is fuming by the end of it, and the kobolds are forced to leave before things get physical. The tribe's heat has increased, but they can try again next month...")
            k.tribe.gain_heat(diff-roll, f)
        else:
            k.tribe.heat_faction[f] -= diff*max(roll-diff, 1)
            if k.tribe.heat_faction[f] <= 0:
                k.p("Thanks to "+n[2].display()+"'s expert negotiation skills, the "+f +
                    " faction and the kobolds have reached an agreement. They call a truce on the condition that the kobolds keep their meddling in the area to a minimum. "+f+" faction members will no longer attack your tribe.")
                if f == "Goblin":
                    spawn_item("Bronze Ingot", k)
                    k.p(
                        "As a sign of comradery, the goblin boss presents [n] with a gift: a Bronze Ingot. Perfect, we might be able to reverse engineer this...")
                k.tribe.shc_faction[f] = 0
            else:
                k.p("Thanks to "+n[2].display()+"'s negotiation skills, the "+bn+" is willing to hear them out, and they've made some significant progress. Heat has decreased, but the " +
                    bn+" isn't willing to call off the raids just yet. The kobolds can try again next month.")
        k.add_trait("goblin_talks")
        return True
    return False


def cmd_gift(words, k, target):
    if k.tribe and k.tribe.gift != 0:
        k.p("[n]'s tribe has already given a gift this month.")
        return False
    p = k.get_place()
    f = None
    if isinstance(p, Tile):
        for l in p.special:
            if landmark_data[l].get("faction", None):
                f = landmark_data[l]["faction"]
                break
    if f:
        v = (target.value/2)-10+k.smod("cha")+k.skmod("negotiation")
        if k.tribe:
            k.tribe.gift = v
        target.destroy("Gifted")
        if f not in k.tribe.heat_faction:
            k.tribe.heat_faction[f] = 0
        if v <= 0:
            k.tribe.gain_heat(v*-1, f)
            k.p("The "+f +
                " folk are offended by [n]'s meager offering! The tribe's heat has increased.")
        else:
            k.tribe.heat_faction[f] = max(
                k.tribe.heat_faction[f]-v, k.tribe.heat_faction[f]/2)
            k.p("The "+f +
                " folk are intrigued by [n]'s offering. The tribe's heat has decreased.")
            if f == "Goblin":
                if "Goblin Language" not in k.tribe.research:
                    i = spawn_item("Goblin Script", k)
                    k.p("The goblins seem to recognize your willingness to negotiate and hand you something in return. It's a tablet filled with strange symbols.")
            else:
                if "Common Language" not in k.tribe.research:
                    i = spawn_item("Common Script", k)
                    k.p("The "+f+" folk seem to recognize your willingness to negotiate and hand you something in return. It's a book filled with strange symbols.")
            for e in k.world.encounters:
                if k.party in e.engaged:
                    fac = True
                    for c in e.creatures:
                        if c.faction != f:
                            fac = False
                    if fac:
                        e.disengage_all()
                        e.hostile = False
                        k.p("Your attackers recognize your peaceful intent and leave you alone.")
        k.gain_xp("negotiation", v+20)
        return True
    k.p("There is no one to receive the gift.")
    return False


def cmd_serve(words, me, target):
    if target not in me.tribe.tavern:
        me.p("That kobold is not in your tavern.")
        return False
    if target.tribe or target.nick:
        me.p("You cannot directly serve a named or tribed kobold; use the !give command if they're asking for something.")
        return False
    p = me.get_place()
    (liquid, source, i) = get_liquid_source(words[2], p, me)
    drank = False
    if not liquid:
        me.p("Fluid source not found.")
    else:
        l = liquid_data[liquid]
        v = l.get("value", 0)
        if v <= 0 or l.get("potion", False):
            me.p("[n] will not drink this.")
            return False
        if i:
            drank = i.drink_from(target)
        elif target.drink(liquid):
            if liquid == "Water" and isinstance(p, Tribe) and source > -1:
                p.water -= 1
                if p.water <= 0:
                    me.p("The well has run dry.")
                console_print("water left: "+str(p.water))
            drank = True
    if drank:
        v = math.floor(
            min(v*(1+((me.smod("cha")+me.skmod("negotiation"))/20)), v*1.5))
        spawn_item("Marble Pebble", me, v)
        if target.has_trait("hungover"):
            me.p(target.display()+" pays [n] "+str(v)+" marble for the " +
                 liquid+" and stumbles their way out of the tavern.")
            me.tribe.tavern.remove(target)
            if target in me.world.kobold_list:
                me.world.kobold_list.remove(target)
        else:
            me.p(target.display()+" pays [n] "+str(v) +
                 " marble for the "+liquid+". They seem satisfied.")
        me.gain_xp("negotiation", v)
    return drank


def cmd_break(words, k, target):
    if not target.has_trait("bound"):
        k.p("That kobold is not a prisoner.")
        return False
    elif target.has_trait("broken"):
        k.p("That kobold is already broken.")
        return False
    exp = 20
    rpower = k.smod("str")+k.smod("cha")+k.skmod("intimidation")
    roll = rpower+random.randint(1, 20)
    roll -= max(target.smod("con"), target.smod("wis")) + \
        int(10*target.hp/target.max_hp)
    if target.age < 6:
        roll += 5
        k.tribe.gain_heat(1)
    console_print(roll)
    k.p("[n] beats down on "+target.display()+".")
    target.hp_tax(2, "Beaten to death", k)
    if target.hp > 0:
        if roll > 10:
            k.p(target.display(
            )+"'s will has been broken. They will follow orders without question.")
            target.add_trait("broken")
            exp *= 2
        else:
            k.p(target.display()+" holds firm.")
    k.gain_xp("intimidation", exp)
    return True


def cmd_release(words, k, target):
    if target in k.tribe.prison and target.d_user_id != 0:
        k.p("[n] frees "+target.display() +
            " of their bindings and moves them along. They make sure to run off before the chieftain changes their mind.")
        target.despawn()
        return True
    else:
        k.p("Must be a prisoner.")
        return False


def cmd_capture(words, k, target):
    if not k.tribe:
        k.p("There is no tribe to capture into.")
        return False
    if not k.tribe.has_building("Prison"):
        k.p("You'll have nowhere to keep them.")
        return False
    if target.has_trait("bound"):
        k.p("That kobold is already a prisoner.")
        return False
    if not target.tribe:
        if not target.nick:
            besti = None
            for i in k.items:
                if i.type == "binding" and (not besti or i.toolpower > besti.toolpower):
                    besti = i
            if not besti:
                k.p("You don't have anything to bind them with.")
                return False
            rpower = k.smod("str")+k.smod("cha") + \
                k.skmod("intimidation")+besti.toolpower
            roll = rpower+random.randint(1, 20)
            if target.age < 6:
                roll += 5
                k.tribe.gain_heat(1)
            if target.encounter:
                roll -= (len(target.encounter.creatures)-1)*3
            else:
                roll -= 4
            if target.has_trait("drunk"):
                roll += target.booze_ap
            if target.has_trait("charmed"):
                roll += rpower
            roll -= max(target.smod("str"), target.smod("dex")) + \
                int(10*target.hp/target.max_hp)
            console_print(roll)
            exp = 35
            if roll > 10:
                exp *= 2
                k.tribe.prison.append(target)
                k.p("[n] has successfully captured "+target.display()+"!")
                drop = list(target.items)
                dest = target.get_place()
                for i in drop:
                    i.move(dest)
                consume_item(k, besti.name)
                if k.party and not isinstance(dest, Tribe):
                    k.party.join(target)
                target.encounter = None
                target.add_trait("bound")
                target.del_trait("trader")
                if target in k.tribe.tavern:
                    k.tribe.tavern.remove(target)
                    k.tribe.add_bold(target)
                for e in k.world.encounters:
                    if target in e.creatures:
                        e.creatures.remove(target)
                        if len(e.creatures) == 0:
                            k.world.encounters.remove(e)
                        elif k.party not in e.engaged:
                            k.p(target.display()+"'s party attacks!")
                            e.start(k.party)
                        break
            else:
                k.p(target.display()+" evades [n]'s capture.")
                if target.encounter:
                    if k.party not in target.encounter.engaged:
                        if len(target.encounter.creatures) > 1 and roll < 6:
                            k.p(target.display(
                            )+": \"You will not take me alive!\"\nThe kobolds attack!")
                            target.encounter.start(k.party)
                        else:
                            k.p(target.display()+": \"Get away from me!\"\n" +
                                target.display()+" flees!")
                            target.despawn()
                if target in k.tribe.tavern:
                    k.p(target.display() +
                        ": \"I never should have come here!\"\n[n] leaves.")
                    target.despawn()
            k.gain_xp("intimidation", exp)
            return True
        else:
            k.p("Cannot capture this kobold: Named kobolds do not stand for that kind of abuse!")
    else:
        k.p("Cannot capture this kobold: they are in another tribe.")


def cmd_rename(words, k, target):
    if not target.owner:
        k.p("Must rename a tamed creature.")
        return False
    name = words[2]
    if len(name) > 32:
        k.p("Name must be 32 characters or shorter.")
        return False
    for c in name:
        if ord(c) > 256:
            k.p("This name contains an illegal character ("+c+").")
            return False
    k.p("[n] has given "+target.display()+" a new name: "+name+".")
    target.name = name
    return True


def cmd_shear(words, k, target):
    if "Wool" not in target.products:
        k.p("This creature cannot produce wool in any usable amount.")
        return False
    if "domestic" not in target.training:
        k.p("This creature will not let you shear it. It needs domestic training first.")
        return False
    if target.has_trait("shorn"):
        k.p("This creature has already been shorn recently.")
        return False
    anipower = k.skmod("animals")+k.smod("cha")
    am = max(1, math.floor(anipower/2))
    spawn_item("Wool", k, am)
    target.add_trait("shorn")
    k.p("[n] shears "+target.display() +
        " and collects "+str(am)+" unit(s) of Wool.")
    if k.accident(15-anipower):
        k.p("[n]'s poor handling of "+target.display() +
            " resulted in the animal kicking back...")
    k.gain_xp("animals", 10+(am*2))
    return True


def cmd_milk(words, k, target):
    if "Milk" not in target.products:
        k.p("This creature cannot produce milk in any usable amount.")
        return False
    if "domestic" not in target.training:
        k.p("This creature will not let you milk it. It needs domestic training first.")
        return False
    if target.has_trait("milked"):
        k.p("This creature has already been milked recently.")
        return False
    anipower = k.skmod("animals")+k.smod("cha")
    am = max(1, math.floor(anipower/4))
    bucket = None
    for i in k.items:
        if i.type == "container" and (not i.liquid or i.liquid == "Milk") and i.liquid_units+am <= i.liquid_capacity:
            bucket = i
            break
    if not bucket:
        k.p("You need a container capable of holding "+str(am)+" unit(s) of milk.")
        return False
    bucket.liquid = "Milk"
    bucket.liquid_units += am
    target.add_trait("milked")
    k.p("[n] milks "+target.display()+" and fills their " +
        bucket.display()+" with "+str(am)+" unit(s) of Milk.")
    if k.accident(15-anipower):
        k.p("[n]'s poor handling of "+target.display() +
            " resulted in the animal kicking back...")
    k.gain_xp("animals", 5+(am*5))
    return True


def cmd_train(words, k, target):
    trainings = ["combat", "guard", "search", "haul", "mount", "domestic"]
    tr = words[2].lower()
    if tr == "mount" and target.stats["str"] < 10:
        k.p("A creature needs at least 10 STR to be capable of serving as a mount.")
        return False
    if tr in trainings:
        if tr not in target.training:
            if target.stats["int"] > len(target.training):
                prog = droll(1, 10)+k.smod("cha")+(k.skmod("animals")*2)+5
                prog = max(1, prog)
                if tr not in target.training_prog:
                    target.training_prog[tr] = 0
                target.training_prog[tr] += prog
                maxprog = (len(target.training)+1)*100
                k.p("[n] has made "+str(prog)+" progress towards "+target.display()+"'s " +
                    tr+" training. ("+str(target.training_prog[tr])+"/"+str(maxprog)+")")
                exp = prog
                if target.training_prog[tr] >= maxprog:
                    k.p(target.display()+"'s "+tr+" training is complete!")
                    target.training.append(tr)
                    exp *= 2
                k.gain_xp("animals", exp)
                return True
            else:
                k.p(target.display()+" is unable to learn any more tricks.")
        else:
            k.p(target.display()+" is already trained in "+tr+".")
    else:
        k.p("Invalid training. Possible training types: "+", ".join(trainings))
    return False


def cmd_slaughter(words, k, target):
    if not target.owner:
        k.p("Must target a tamed creature.")
        return False
    k.p("[n] approaches "+target.display()+" calmly...")
    target.die(k)
    return True


async def cmd_feeder(words, k, target):
    if words[1].lower() == "add":
        if "Kennel" not in k.tribe.buildings:
            k.p("There is no feeder to add things to.")
            return False
        scope = "any"
    elif words[1].lower() == "remove":
        scope = "kennel"
    item = await multi_select(discord.utils.get(guild.channels, name=k.get_chan()), "", k, place=scope, type="bait/food/material")
    if item:
        if scope == "any":
            item.move(k.tribe.kennel_items)
            k.p("[n] adds the "+item.display()+" to the kennel feeder.")
        else:
            item.move(k)
            k.p("[n] takes the "+item.display()+" out of the kennel feeder.")
            console_print(item.place)
        return True
    return False


async def cmd_tame(words, k, target):
    if isinstance(target, Kobold):
        k.p("You can't tame a kobold.")
    elif target.owner:
        k.p("That creature is already tamed.")
    elif not target.encounter or not target.companion:
        k.p("That creature is not tameable.")
    elif target.stats["int"] > 5:
        k.p("That creature is intelligent. You will have to use the !recruit command (not yet implemented for this purpose)")
    elif target.encounter.hostile:
        k.p("That creature is hostile to you. You need to pacify it first (using !pacify in combat).")
    else:
        bait = await multi_select(discord.utils.get(guild.channels, name=k.get_chan()), "", k, place="inv", type="bait/food/material")
        good = False
        if bait:
            for b in target.diet:
                cat = b.replace("*", "")
                if cat == bait.name or (cat in item_cats and bait.name in item_cats[cat]):
                    good = True
        if bait and good:
            k.p("[n] approaches "+target.display() +
                " calmly, holding out the "+bait.name+".")
            bait.num -= 1
            if bait.num <= 0:
                bait.destroy("Bait")
            rpower = k.smod("cha")+(k.skmod("animals")*2)
            roll = rpower + \
                random.randint(
                    1, 20)-target.stats["int"]-(target.cr*2)-len(target.encounter.creatures)
            console_print(roll)
            exp = roll
            if roll > 10:
                k.p("[n] has successfully tamed "+target.display()+"!")
                target.owner = k
                target.name = kobold_name()
                target.del_trait("pacified")
                k.p("[n] has given it the name "+target.name +
                    " for now; you can rename it with !rename.")
                k.party.join(target)
                if target in target.encounter.creatures:
                    target.encounter.creatures.remove(target)
                if len(target.encounter.creatures) <= 0 and target.encounter in k.world.encounters:
                    k.world.encounters.remove(target.encounter)
                target.encounter = None
                exp += exp+(target.cr*2)
            elif roll > 0:
                k.p(target.display()+" rejects [n]'s offer.")
            else:
                k.p(target.display()+" seems offended and attacks!")
                target.encounter.hostile = True
                target.encounter.start(k.party)
            k.gain_xp("animals", max(0, exp)+10)
            return True
        else:
            k.p("[n] doesn't have any bait that " +
                target.display()+" would be interested in.")
    return False


def cmd_recruit(words, k, target):
    if not k.tribe:
        k.p("There is no tribe to recruit into.")
        return False
    if not target.tribe:
        if not target.nick:
            if not target.has_trait("trader"):
                if not target.has_trait("broken"):
                    rpower = k.smod("cha")+k.skmod("negotiation")
                    roll = rpower+random.randint(1, 20)
                    if target.age < 6:
                        roll += 5
                    if target.encounter:
                        roll -= (len(target.encounter.creatures)-1)*3
                    else:
                        roll -= 4
                    if target.has_trait("drunk"):
                        roll += target.booze_ap
                    if target.has_trait("charmed"):
                        roll += rpower
                    if target.has_trait("bound"):
                        roll -= (10-int(10*(target.hp/target.max_hp)))+5
                    if target.lastchief == k:
                        roll += 100
                        exp = 0
                    else:
                        exp = 35
                    console_print(roll)
                    if roll > 10:
                        exp *= 2
                        target.tribe = k.tribe
                        k.p("[n] has succeeded in recruiting " +
                            target.display()+" to "+k.tribe.name+"!")
                        if k.party and not isinstance(target.get_place(), Tribe):
                            k.party.join(target)
                        target.encounter = None
                        if target in k.tribe.tavern:
                            k.tribe.tavern.remove(target)
                            k.tribe.add_bold(target)
                        if target in k.tribe.prison:
                            k.tribe.prison.remove(target)
                            target.del_trait("bound")
                        for e in k.world.encounters:
                            if target in e.creatures:
                                e.creatures.remove(target)
                                if len(e.creatures) == 0:
                                    k.world.encounters.remove(e)
                                break
                    else:
                        k.p("[n] has failed to recruit "+target.display()+".")
                        if target.encounter:
                            if len(target.encounter.creatures) > 1 and roll < 6:
                                k.p(target.display(
                                )+": \"How dare you? I would rather die than betray my tribe!\"\nThe kobolds attack!")
                                target.encounter.start(k.party)
                        if target in k.tribe.tavern and not chance(roll*10):
                            k.p(target.display(
                            )+": \"I didn't come here to get coerced into changing tribes.\"\n"+target.display()+" leaves.")
                            target.despawn()
                    k.gain_xp("negotiation", exp)
                    return True
                else:
                    k.p("Cannot recruit this kobold: their will has already been broken.")
            else:
                k.p("Cannot recruit this kobold: they are a trader.")
        else:
            k.p("Cannot recruit this kobold: they are named. If you want to add this kobold to your tribe, your chieftain must invite them with `!tribe invite`.")
    else:
        k.p("Cannot recruit this kobold: they are in another tribe.")


def cmd_sell(words, k, target):
    if target.has_trait("trader"):
        if len(target.items) < target.inv_size:
            for i in k.items:
                if words[1].lower() in i.display().lower():
                    if k.party:
                        best = k.party.best_trader()
                    else:
                        best = k.best_trader()
                    multi = best[0]
                    if target.has_trait("charmed"):
                        multi *= 1.1
                    v = int((1/multi)*i.realvalue/2)
                    if v > 0:
                        spawn_item("Marble Pebble", k, v)
                        i.move(target, tumble=True)
                        k.p("[n] has sold their "+i.display() +
                            " for <:marblecoin:933132540926111814>"+str(v)+".")
                        k.p(target.display() +
                            ": \"Pleasure doing business with you!\"")
                        i.sold = True
                        best[2].gain_xp("negotiation", v)
                        return True
                    else:
                        k.p("The trader will not buy that.")
                        return False
            k.p("[n] doesn't have that.")
        else:
            k.p("The trader can't carry any more stuff.")
    else:
        k.p("Can't sell to this kobold.")
    return False


def cmd_buy(words, k, target):
    if target.has_trait("trader"):
        for i in target.items:
            if words[1].lower() in i.display().lower():
                if i.sold:
                    k.p(target.display()+": \"Sorry, I have plans for this.\"")
                    return False
                elif len(k.items) >= k.inv_size:
                    k.p("You have no room in your inventory to buy this.")
                    return False
                else:
                    if i.inv_size > 0:
                        for h in k.items:
                            if h.inv_size > 0:
                                k.p("Can only carry one item that increases inventory size.")
                                return False
                    if k.party:
                        best = k.party.best_trader()
                    else:
                        best = k.best_trader()
                    multi = best[0]
                    if target.has_trait("charmed"):
                        multi *= 1.1
                    v = int(multi*i.realvalue)
                    if k.has_trait("polished") and k.has_item("Stone Pebble", v):
                        money = "Stone Pebble"
                        k.p("[n]'s enchantment makes their ordinary stone pebbles shimmer like marble...")
                    else:
                        money = "Marble Pebble"
                    if k.has_item(money, v):
                        k.consume_item(money, v)
                        i.move(k)
                        k.p("[n] has purchased a "+i.display() +
                            " for <:marblecoin:933132540926111814>"+str(v)+".")
                        k.p(target.display() +
                            ": \"Pleasure doing business with you!\"")
                        best[2].gain_xp("negotiation", v)
                        return True
                    else:
                        k.p("Can't afford "+i.display()+".")
                        return False
        k.p("The trader doesn't have that.")
    else:
        k.p("Can't buy from this kobold.")
    return False


def cmd_trade(words, k, target):
    if target.has_trait("trader"):
        if len(target.items) > 0:
            msg = target.display()+": \"Interested in any of these fine items?\"\n\n"
            if k.party:
                multi = k.party.best_trader()[0]
            else:
                multi = k.best_trader()[0]
            if target.has_trait("charmed"):
                multi *= 1.1
            msg += target.show_wares(multi)+"\n\n"
            msg += k.show_wares(1/multi, True)
        else:
            msg = target.display()+": \"Sorry. I have nothing to trade.\""
        k.p(msg)
        return True
    k.p("Can't trade with this kobold.")
    return False


def cmd_tribename(words, k, target):
    for c in words[1]:
        if len(c) > 1 or ord(c) > 256:
            k.p("This name contains an illegal character ("+c+").")
            return False
    if len(words[1]) > 32:
        k.p("Cannot be longer than 32 characters.")
        return False
    k.tribe.name = words[1]
    k.p("[n] has renamed this tribe to "+words[1]+".")
    return True


def cmd_tavopen(words, k, target):
    if "open" in words[0] and k.tribe.tavern_open:
        k.p("The tavern is already open.")
        return False
    if "close" in words[0] and not k.tribe.tavern_open:
        k.p("The tavern is already closed.")
        return False
    if not k.tribe.tavern_open:
        k.tribe.tavern_open = True
        k.p("The tavern is now open.")
    else:
        k.tribe.tavern_open = False
        k.p("The tavern is now closed.")
    return True


def cmd_tavkick(words, k, target):
    if target.tribe != k.tribe and target in k.tribe.tavern:
        if target.party:
            target = target.party.owner
        k.p(target.display()+" and their party have been kicked from the tavern.")
        cmd_leave([], target, None)
        if target.nick:
            target.p(
                k.display()+" has kicked you and your party from the tavern.", True)
        return True
    else:
        k.p("The target must be in a different tribe and in your tavern.")
    return False


def cmd_tavban(words, k, target):
    if target.tribe != k.tribe and target in k.tribe.tavern:
        if target.party:
            target = target.party.owner
        k.p(target.display()+" and their party have been banned from the tavern.")
        cmd_leave([], target, None)
        if target.nick:
            target.p(
                k.display()+" has banned you and your party from the tavern.", True)
        k.tribe.banned.append(target.id)
        return True
    else:
        k.p("The target must be in a different tribe and in your tavern.")
    return False


def cmd_tavunban(words, k, target):
    if target.id in k.tribe.banned:
        k.p(target.display()+" has been unbanned from [n]'s tavern.")
        if target.nick:
            target.p(k.display()+" has unbanned you from their tavern.", True)
        k.tribe.banned.remove(target.id)
        return True
    else:
        k.p("Must target a kobold banned from your tavern.")
    return False


def cmd_exile(words, k, target):
    target = find_kobold(words[1], w=k.world)
    if target:
        if target.tribe == k.tribe:
            if k != target:
                if not k.has_trait("chief_exile") or not target.nick:
                    p = target.get_place()
                    q = k.get_place()
                    if q == k.tribe or q == p:
                        if p == target.tribe:
                            k.p("[n] has exiled "+target.display() +
                                ". They are forced to forfeit all items and leave the den.")
                            for i in target.items:
                                i.move(k.tribe)
                            if target.party:
                                target.party.leave(target)
                            cmd_leave([], target, None)
                            if target.nick:
                                target.party = Party(target)
                                game_print(
                                    "You have been exiled! You will either need to find a new tribe or live a nomadic lifestyle...", target.party.get_chan())
                        elif q != k.tribe and q == p:
                            k.p("[n] has exiled "+target.display() +
                                ". They will no longer be able to return to their home tribe.")
                        else:
                            k.p("[n] has exiled "+target.display() +
                                ". They will no longer be able to return.")
                            if target.party:
                                target.p(
                                    "[n] gets the strangest feeling that they are no longer welcome in their home tribe.")
                        target.tribe = None
                        if target.nick:
                            k.add_trait("chief_exile")
                        exed = get_pdata(target.d_user_id, "exiled_from", [])
                        exed.append(k.tribe.id)
                        target.lastchief = k
                        return True
                    else:
                        k.p("You must either execute this action from the den, or in the same area as the target.")
                else:
                    k.p("You have already exiled a named kobold this month.")
            else:
                k.p("You can't exile yourself.")
        else:
            k.p("Must target a kobold from your own tribe.")
    else:
        k.p("Target kobold '"+words[1]+"' not found.")
    return False


def cmd_lock(words, k, target):
    if target.tribe == k.tribe and not target.nick:
        if target.has_trait("locked"):
            target.del_trait("locked")
            k.p(target.display()+" is no longer locked.")
            return True
        if not target.d_user_id:
            p = k.tribe.get_population()
            if p[1] < math.floor(p[0]/3):
                target.add_trait("locked")
                k.p(target.display() +
                    " is locked and can no longer be named by a new player.")
                return True
            else:
                k.p("Your tribe has already reached the maximum amount of locked kobolds (have " +
                    str(p[1])+", max is "+str(math.floor(p[0]/3))+"). Unlock some kobolds first.")
        else:
            k.p("Can't lock this kobold (they belong to another player who quit)")
    else:
        k.p("Must select a nameless kobold in your tribe.")
    return False


def cmd_overseer(words, k, target):
    if target.tribe == k.tribe and target.nick:
        if k.tribe.overseer != target:
            if not k.has_trait("chief_overseer"):
                k.tribe.overseer = target
                k.p("[n] has appointed "+target.display() +
                    " as the tribe's Overseer.")
                k.add_trait("chief_overseer")
                return True
            else:
                k.p("You have already appointed an overseer this month.")
        else:
            k.p("That kobold is already the overseer.")
    else:
        k.p("Must appoint a named kobold from your tribe.")
    return False


def cmd_ce(words, k, target):
    celist = k.tribe.get_available_research()+k.tribe.get_available_builds()
    vote = None
    for c in celist:
        if words[1].lower() in c.lower():
            vote = c
            break
    if not vote:
        k.p("No available research or building '" +
            words[1]+"'. Make sure that you have all requirements and materials in storage.")
        return False
    k.ce = vote
    k.p("[n] votes for "+k.ce+" as the Community Effort project.")
    return True


def cmd_elect(words, k, target):
    if words[1].lower() in ["none", "abstain"]:
        k.vote = -1
        k.p("[n] is abstaining from the Chieftain election.")
        return True
    target = find_kobold(words[1], w=k.world)
    if target and target.tribe == k.tribe and target.nick:
        k.vote = target.id
        k.p("[n] wants "+target.display()+" to be the Chieftain.")
        return True
    else:
        k.p("Must vote for a named kobold in your tribe.")
    return False


def cmd_familiarity(words, k, target):
    fams = {"Learning": [], "Familiar": [], "Very Familiar": []}
    for f in target.familiarity:
        r = find_research(f)
        fl = target.familiar(f)
        if fl == 0:
            fstr = "Learning"
        elif fl == 1:
            fstr = "Familiar"
        else:
            fstr = "Very Familiar"
        if fl < 2:
            fams[fstr].append(
                f+" - "+str(target.familiarity[f])+"/"+str(r["diff"]*(fl+1)))
        else:
            fams[fstr].append(f)
    msg = ""
    for f in fams:
        msg += f+":\n"+"; ".join(fams[f])+"\n\n"
    action_queue.append(["embed", k.get_chan(), discord.Embed(
        type="rich", title="Familiarity: "+target.display(), description=msg)])
    return True


async def cmd_look(words, k, chan):
    if len(words) < 2:
        place = k.get_place()
        if k.party:
            for e in k.world.encounters:
                if e.place == place:
                    e.examine(k)
        place.examine(k)
    else:
        if words[1] == "self":
            target = k
        else:
            target = find_kobold(words[1], k.get_place(), k.world)
        if target:
            target.char_info(k)
        else:
            target = find_creature_i(words[1], k)
            if target:
                target.char_info(k)
            else:
                target = await multi_select(chan, words[1], k)
                if target:
                    target.examine(k)
    return True


async def cmd_lookall(words, me, chan):
    p = me.get_place()
    bolds = []
    for k in me.world.kobold_list:
        if k.get_place() == p:
            bolds.append(k)
    embeds = []
    for k in bolds:
        e = discord.Embed(type="rich", title="Kobold info: " +
                          k.display(), description=k.char_info(me, pr=False))
        embeds.append(e)
        e.set_footer(text="Showing kobold "+str(len(embeds))+" of " +
                     str(len(bolds))+". React to scroll through results.")
    await embed_group(chan, embeds)
    return True


async def cmd_items(words, me, chan):
    t = me.get_place()
    inv = {"all": {}}
    for i in t.items:
        dis = i.display()
        if len(words) > 1 and (words[1].lower() not in dis.lower() and words[1].lower() != i.type):
            continue
        if i.name in inv["all"]:
            inv["all"][i.name] += i.num
        else:
            inv["all"][i.name] = i.num
        if i.type not in inv:
            inv[i.type] = {}
        if dis in inv[i.type]:
            inv[i.type][dis] += 1
        else:
            inv[i.type][dis] = 1
    embeds = []
    index = 1
    for v in inv:
        winv = []
        m = sorted(inv[v].items(), key=lambda kv: kv[0])
        for i in m:
            if i[1] > 1:
                winv.append(i[0]+" ("+str(i[1])+")")
            else:
                winv.append(i[0])
        e = discord.Embed(type="rich", title="Items here (" +
                          v+")", description=", ".join(winv))
        e.set_footer(text="Showing page "+str(index)+" of " +
                     str(len(list(inv.keys())))+". React to scroll.")
        embeds.append(e)
        index += 1
    await embed_group(chan, embeds)
    return True


def cmd_bio(words, me, target):
    e = discord.Embed(type="rich", title=target.display(),
                      description=target.bio)
    action_queue.append(["embed", me.get_chan(), e])
    return True


def cmd_flavor(words, me, i):
    if len(words[1]) > 1000:
        me.p("Bio must be 1000 characters or less.")
        return False
    me.bio = words[1]
    me.p("Bio for [n] set.")
    return True


async def cmd_say(words, me, chan):
    if len(words[1]) > 1000:
        await chan.send("Message must be 1000 characters or less.")
        return False
    msg = me.display()+": \""+words[1]+"\""
    await chan.send(msg)
    if me.party:
        me.party.broadcast(msg)
    return True


async def cmd_me(words, me, chan):
    if len(words[1]) > 1000:
        await chan.send("Message must be 1000 characters or less.")
        return False
    words[1] = words[1].replace("*", "\*")
    msg = "*"+me.display()+" "+words[1]+"*"
    await chan.send(msg)
    if me.party:
        me.party.broadcast(msg)
    return True


def cmd_getoff(words, me, k):
    for l in me.world.kobold_list:
        if l.carry == me:
            cmd_setdown(words, l, me)
            return True
        if not l.party:
            continue
        for c in l.party.c_members:
            if c.carry == me:
                cmd_setdown(words, c, me)
                return True
    if me.has_trait("carried"):
        me.p("Your ride seems to no longer be of this world... Don't worry, I'll fix it for you.")
    else:
        me.p("You are not being carried.")
    me.del_trait("carried")
    return False


def cmd_setdown(words, me, k):
    if not me.carry:
        me.p("[n] is not carrying a kobold.")
        return False
    if isinstance(me.get_place(), Tribe):
        me.get_place().add_bold(me.carry)
    elif me.party and not me.carry.party and me.carry.age > 0:
        me.party.join(me.carry)
    me.p("[n] sets down "+me.carry.display()+".")
    me.carry.del_trait("carried")
    me.carry = None
    return True


def cmd_mount(words, k, me):
    if "mount" not in me.training:
        k.p(me.display()+" needs mount training before they can be mounted.")
        return False
    if len(me.items) >= me.inv_size:
        k.p(me.display()+"'s inventory is full.")
        return False
    elif me.carry:
        k.p(me.display()+" is already carrying a kobold.")
        return False
    elif me.owner.tribe != k.tribe:
        k.p("Can't mount a creature from another tribe.")
        return False
    elif k.carry:
        k.p("Can't mount a creature if you're carrying a kobold.")
        return False
    elif k.party and k.party != me.party:
        k.p("Can't mount a creature in a party that is not yours.")
        return False
    me.carry = k
    if k.nick:
        if me.party and k not in me.party.members:
            if k.party:
                k.party.leave(k, reform=False)
            me.party.join(k)
    else:
        if me.party and k in me.party.members:
            me.party.leave(k)
    k.p("[n] mounts "+me.display()+".")
    k.add_trait("carried")
    return True


def cmd_carry(words, me, k):
    if len(me.items) >= me.inv_size:
        me.p("[n]'s inventory is full.")
        return False
    elif me.carry:
        me.p("[n] is already carrying a kobold.")
        return False
    elif (isinstance(me, Creature) and me.owner.tribe != k.tribe) or (isinstance(me, Kobold) and me.tribe != k.tribe):
        me.p("Can't pick up a kobold from another tribe.")
        return False
    elif k.carry:
        me.p("Can't pick up a kobold who is themselves carrying someone.")
        return False
    elif k.nick and not k.has_trait("rescues"):
        me.p("Can't pick up a named kobold who doesn't want to be rescued. (The target needs to allow rescues with `!rescues` first)")
        return False
    elif k.party and k.party != me.party:
        me.p("Can't pick up a kobold in a party that is not yours.")
        return False
    for l in me.world.kobold_list:
        if l.carry == k:
            me.p(k.display()+" is already being carried.")
            return False
    me.carry = k
    if k.nick:
        if me.party and k not in me.party.members:
            if k.party:
                k.party.leave(k, reform=False)
            me.party.join(k)
    else:
        if me.party and k in me.party.members:
            me.party.leave(k)
    me.p("[n] picks up "+k.display()+".")
    k.add_trait("carried")
    return True


def cmd_empty(words, me, i):
    if i.contains:
        me.p("[n] removes the "+i.contains.display() +
             " from the "+i.display()+".")
        if len(me.items) < me.inv_size:
            i.contains.move(me)
        else:
            i.contains.move(me.get_place())
    elif i.liquid:
        p = me.get_place()
        if i.liquid == "Water" and isinstance(p, Tribe) and p.has_building("Well"):
            p.water += i.liquid_units
            if p.water > p.water_max:
                p.water = p.water_max
            me.p("[n] empties the "+i.display()+" into the well.")
        else:
            me.p("[n] empties the "+i.display()+".")
        i.liquid = False
        i.liquid_units = 0
        return True
    else:
        me.p("There is nothing to empty.")
        return False


def get_liquid_source(liq, p, me):
    liquid = None
    source = 0
    i = None
    if liq.lower() == "water" and isinstance(p, Tribe) and p.has_building("Well"):
        liquid = "Water"
        source = p.water
    else:
        if not isinstance(p, Tribe):
            for l in p.special:
                if l not in landmark_data:
                    continue
                if landmark_data[l].get("liquid_source", None) and liq.lower() == landmark_data[l]["liquid_source"].lower():
                    liquid = landmark_data[l]["liquid_source"]
                    source = -1
                    break
        if not liquid:
            scope = me.items+me.get_place().items
            for i in scope:
                if i.liquid and liq.lower() in i.liquid.lower() and i.liquid_units > 0:
                    liquid = i.liquid
                    source = i.liquid_units
                    break
    return (liquid, source, i)


def cmd_drink(words, me, lol):
    p = me.get_place()
    (liquid, source, i) = get_liquid_source(words[1], p, me)
    if not liquid:
        me.p("Fluid source not found.")
    elif isinstance(p, Tribe) and me in p.tavern and (not i or i not in me.items):
        me.p("While in a tavern, you can only drink from containers in your inventory.")
        return
    elif i:
        return i.drink_from(me)
    elif me.drink(liquid):
        if liquid == "Water" and isinstance(p, Tribe) and source > -1:
            p.water -= 1
            if p.water <= 0:
                me.p("The well has run dry.")
            console_print("water left: "+str(p.water))
        return True
    return False


async def cmd_fill(words, me, chan):
    p = me.get_place()
    drained = 0
    h = await multi_select(chan, words[1], me, type="container")
    if h:
        if h.liquid_capacity == 0:  # food container
            if h.contains:
                me.p(h.display()+" already contains "+h.contains.display()+".")
                return False
            i = await multi_select(chan, words[2], me, type="food")
            if i:
                i.move(h)
                me.p("[n] stores their "+h.contains.display() +
                     " in the "+h.display()+".")
                return True
        else:
            (liquid, source, i) = get_liquid_source(words[2], p, me)
            if not liquid:
                me.p("Fluid source not found.")
                return False
            if (h.liquid == liquid or not h.liquid) and h.liquid_units < h.liquid_capacity:
                h.liquid = liquid
                while source != 0 and h.liquid_units < h.liquid_capacity:
                    source -= 1
                    h.liquid_units += 1
                    drained += 1
                if i:
                    i.liquid_units -= drained
                    if i.liquid_units <= 0:
                        i.liquid = None
                elif liquid == "Water" and isinstance(p, Tribe) and source > -1:
                    p.water -= drained
                    if p.water <= 0:
                        me.p("The well has run dry.")
                    console_print("water left: "+str(p.water))
                me.p("[n] fills their "+h.display()+" with " +
                     str(drained)+" unit(s) of "+liquid+".")
                return True
    me.p("Must target a container.")
    return False


def cmd_give(words, me, i):
    target = find_kobold(words[1].lower(), me.get_place(), me.world)
    if not target:
        target = find_creature_i(words[1].lower(), me)
        if not target:
            me.p("Kobold '"+words[1]+"' not found.")
            return False
        elif "haul" not in target.training:
            me.p(target.display()+" needs haul training to be able to carry items.")
            return False
    if len(target.items) >= target.inv_size:
        good = False
        for h in target.items:
            if h.name == i.name and h.num+i.num <= i.stack:
                good = True
        if not good:
            me.p(target.display()+"'s inventory is full.")
            return False
    if i.inv_size > 0:
        for h in target.items:
            if h.inv_size > 0:
                me.p("Can only carry one item that increases inventory size.")
                return False
    am = i.num
    if len(words) > 3:
        if words[3] < 0 or words[3] > i.num:
            me.p("If specifying a number, must be above 0 and below the amount contained in the item stack.")
            return False
        else:
            am = words[3]
    if i in me.items:
        msg = me.display()+" gives "+target.display()+" the "+i.display()+"."
        if am >= i.num:
            i.move(target)
        else:
            i.num -= am
            spawn_item(i.name, target, am)
            msg = me.display()+" gives "+target.display()+" "+i.name+" x"+str(am)+"."
        me.p(msg)
        if me.party:
            me.party.broadcast(msg)
        return True
    else:
        me.p("[n] doesn't have that.")
    return False


def cmd_scoop(words, me, i):
    if len(words) > 1:
        targets = find_item_multi(
            words[1].lower(), me, False, "ground", ignore_displays=True)
    else:
        targets = list(me.get_place().items)
    for i in targets:
        good = cmd_get([], me, i)
        if not good:
            break
    return True


def cmd_get(words, me, i):
    am = i.num
    if len(words) > 2:
        if words[2] < 0 or words[2] > i.num:
            me.p("If specifying a number, must be above 0 and below the amount contained in the item stack.")
            return False
        else:
            am = words[2]
    if len(me.items) >= me.inv_size:
        good = False
        for h in me.items:
            if h.name == i.name and h.num+am <= i.stack:
                good = True
        if not good:
            me.p("[n]'s inventory is full.")
            return False
    if i.inv_size > 0:
        for h in me.items:
            if h.inv_size > 0:
                me.p("Can only carry one item that increases inventory size.")
                return False
    t = me.get_place()
    if isinstance(t, Tribe) and me in t.tavern:
        t = me.world.get_tile(me.x, me.y, me.z)
    if i in t.items:
        msg = me.display()+" picks up the "+i.display()+"."
        if am >= i.num:
            i.move(me)
        else:
            i.num -= am
            spawn_item(i.name, me, am)
            msg = me.display()+" picks up "+i.name+" x"+str(am)+"."
        me.p(msg)
        if me.party:
            me.party.broadcast(msg)
        return True
    else:
        me.p("[n] already has that.")
    return False


def cmd_dropall(words, me, i):
    drops = list(me.items)
    dropped = False
    for d in drops:
        if (len(words) == 1 or words[1] != "eq") and not isinstance(me, Creature):
            if d.inv_size > 0:
                continue
            if d == me.equip or d in list(me.worns.values()):
                continue
        cmd_drop(words, me, d)
        dropped = True
    if not dropped:
        me.p("[n] has nothing to drop.")
    return True


def cmd_drop(words, me, i):
    am = i.num
    if len(words) > 2:
        if words[2] < 0 or words[2] > i.num:
            me.p("If specifying a number, must be above 0 and below the amount contained in the item stack.")
            return False
        else:
            am = words[2]
    t = me.get_place()
    if isinstance(t, Tribe) and me in t.tavern:
        t = me.world.get_tile(me.x, me.y, me.z)
    if i in me.items:
        msg = me.display()+" drops the "+i.display()+"."
        if am >= i.num:
            i.move(t)
        else:
            i.num -= am
            spawn_item(i.name, t, am)
            msg = me.display()+" drops "+i.name+" x"+str(am)+"."
        me.p(msg)
        if me.party:
            me.party.broadcast(msg)
        return True
    else:
        me.p("[n] doesn't have that.")
    return False


def cmd_comfort(words, me, target):
    saves = []
    for t in target.traits:
        if trait_data[t].get("comfort_save_to_cure", False):
            saves.append(t)
    base = max(me.smod("cha"), me.smod("wis"))+me.skmod("willpower")
    exp = (base+4)*4
    if len(saves) > 0:
        me.p("[n] sits with "+target.display() +
             " and tries to work through their problems.")
        s = choice(saves)
        if target.save(trait_data[s]["save_stat"])+base >= trait_data[s]["save"]:
            me.p(target.display()+" has been cured of their " +
                 trait_data[s].get("display", s)+" condition.")
            target.del_trait(s)
            exp *= 2
        else:
            me.p("[n] fails to break through to "+target.display()+".")
    elif not target.has_trait("relaxed"):
        if base <= 0:
            me.p("[n] doesn't have the skill to relax " +
                 target.display()+" any further.")
            return False
        me.p("[n] reassures "+target.display() +
             " that they can accomplish great things.")
        if chance(5*base):
            target.add_trait("relaxed")
        else:
            me.p(target.display()+" doesn't seem receptive.")
    else:
        me.p(target.display()+" doesn't need comforting.")
        return False
    me.gain_xp("willpower", exp)
    return True


def cmd_cheer(words, me, target):
    if not (target.nick and me.nick):
        me.p("Only a named kobold can do this, and the target must be another named kobold.")
        return False
    elif target.cp >= target.max_cp:
        me.p(target.display()+" is at max CP.")
        return False
    base = me.smod("cha")+me.skmod("willpower")
    am = random.randint(1, max(1, base))
    exp = ((am+base)*2)+5
    target.cp += am
    if target.cp > target.max_cp:
        target.cp = target.max_cp
    me.p("[n] cheers for "+target.display()+", giving them "+str(am)+" CP.")
    me.gain_xp("willpower", exp)
    return True


def cmd_heal(words, me, target):
    cond = False
    for t in target.traits:
        if trait_data[t].get("heal_save_to_cure", False):
            cond = True
    if target.hp < target.max_hp or cond:
        bestmed = None
        beststr = 0
        exp = 0
        for i in me.items:
            if i.type == "medicine" and i.hp > beststr:
                beststr = i.hp
                bestmed = i
        base = 2+me.smod("wis")+math.floor(me.skmod("medicine")/2)
        if base <= 0:
            heal = 0
        else:
            heal = random.randint(0, base)
        if bestmed:
            heal += bestmed.hp
            ch = abs(bestmed.quality)*20
            if chance(ch):
                if bestmed.quality > 0:
                    heal += 1
                if bestmed.quality < 0:
                    heal -= 1
            bestmed.destroy("Medicine")
            if target.hp == target.max_hp:
                heal += 2  # small mercy boost for already being at max health
            for t in target.traits:
                if trait_data[t].get("heal_save_to_cure", False):
                    if target.save(trait_data[t]["save_stat"])+heal >= trait_data[t]["save"]:
                        target.del_trait(t)
                        target.p("[n] has been cured of their " +
                                 trait_data[t].get("display", t)+" condition.")
                        heal -= 5
                        if heal < 1:
                            heal = 1
                        exp += trait_data[t]["save"]*4
                        break
        else:
            heal = math.floor(heal/2)
            if heal > math.ceil(target.max_hp/5):
                heal = math.ceil(target.max_hp/5)
        exp = (heal+4)*4
        if heal > 0:
            me.p("[n] heals "+target.display()+" for "+str(heal)+" HP.")
            target.hp_gain(heal)
        else:
            me.p("[n] tries to heal "+target.display() +
                 " but fails to do anything useful.")
        for t in target.traits:
            if trait_data[t].get("heal_save_to_cure", False) and not trait_data[t].get("visible", False):
                if bestmed:
                    me.p("[n] has discovered "+target.display()+"'s " +
                         trait_data[t].get("display", t)+" condition, but fails to treat it.")
                else:
                    me.p("[n] has discovered "+target.display()+"'s "+trait_data[t].get(
                        "display", t)+" condition, but cannot treat it without medicine.")
        me.gain_xp("medicine", exp)
        return True
    else:
        me.p(target.display()+" is at full HP.")
    return False


def cmd_rally(words, me, target):
    if len(me.party.k_members) <= 1:
        me.p("There is no one to inspire.")
        return False
    ch = 25+((me.smod("cha")+me.skmod("command"))*5)
    me.p("[n] takes charge and starts talking battle tactics.")
    bolds = list(me.party.k_members)
    random.shuffle(bolds)
    am = max(1, me.smod("cha")+1)
    exp = 10
    for k in bolds:
        if k == me or k.has_trait("inspired"):
            continue
        if chance(ch):
            k.add_trait("inspired")
            k.p("[n] is feeling inspired!")
            am -= 1
            exp += 10
            ch -= 10
            if am <= 0:
                break
    if exp == 10:
        me.p("Their words don't seem to reach their allies, however.")
    me.gain_xp("command", exp)
    return True


def cmd_guard(words, me, target):
    target.aggro = True
    me.aggro = True
    target.guardian = me
    me.p("[n] stands in front of "+target.display()+" and braces themselves.")
    return True


def cmd_pass(words, me, target):
    me.aggro = False
    me.p("[n] waits.")
    return True


def cmd_dodge(words, me, target):
    me.aggro = False
    me.add_trait("dodging")
    me.p("[n] gets ready to dodge.")
    return True


def cmd_fight(words, me, target):
    enc = None
    for e in me.world.encounters:
        if e.place == me.get_place():
            enc = e
            break
    if not enc:
        me.p("There is nothing to fight.")
        return False
    if enc.special:
        me.p("The party engages! Combat is initiated!")
        enc.start(me.party)
        return True
    stealth = 0
    for k in me.party.k_members:
        stealth += random.randint(1, 20)+k.stealth
    stealth = int(stealth/len(me.party.k_members))-len(me.party.members)+1
    percep = 0
    for c in enc.creatures:
        percep += random.randint(1, 20)+c.smod("wis")
    percep = int(percep/len(enc.creatures))-len(enc.creatures)+1
    if stealth >= percep:
        me.p("The party takes the enemy by surprise!")
        for c in enc.creatures:
            c.add_trait("surprised")
        exp = percep
    else:
        me.p("The party tries to stage an ambush but are spotted. Combat is initiated!")
        exp = stealth
    enc.start(me.party)
    for k in me.party.k_members:
        k.gain_xp("stealth", exp)


def cmd_attack(words, me, target):
    melee = True
    if isinstance(me, Creature):
        me.attack(target)
        return True
    elif me.equip and me.equip.type in ["melee", "ranged", "magic", "finesse"]:
        me.dmg = list(me.equip.dmg)
        eqtype = me.equip.type
        if me.equip.quality != 0:
            ch = abs(me.equip.quality)*20
            if chance(ch):
                if me.equip.quality > 0:
                    me.dmg[2] += 1
                if me.equip.quality < 0:
                    me.dmg[2] -= 1
        me.dmgtype = me.equip.dmgtype
        if me.equip.type == "melee":
            me.dmg[2] += me.smod("str")
            me.tohit = me.smod(
                "str")+math.ceil((me.skmod("melee")+random.randint(0, 1))/2)
        elif me.equip.type == "finesse":
            bonus = max(me.smod("str"), me.smod("dex"))
            me.dmg[2] += bonus
            me.tohit = bonus + \
                math.ceil((me.skmod("melee")+random.randint(0, 1))/2)
        elif me.equip.type == "magic":
            melee = False
            if not me.mp_tax(1):
                return False
            me.dmg[2] += me.smod("int")
            me.tohit = me.smod(
                "int")+math.ceil((me.skmod("sorcery")+random.randint(0, 1))/2)
        else:
            melee = False
            ammo = False
            for i in me.items:
                if i.type == "ammo" and me.equip.ammunition in i.name.lower():
                    consume_item(me, i.name, 1)
                    for d in range(3):
                        me.dmg[d] += i.dmg[d]
                    ammo = True
                    break
            if not ammo:
                me.p("Out of ammo!")
                return False
            me.dmg[2] += me.smod("dex")
            me.tohit = me.smod(
                "dex")+math.ceil((me.skmod("marksman")+random.randint(0, 1))/2)
        me.equip.lower_durability()
    else:
        me.dmg = [0, 0, max(1, me.smod("str")+1)]
        # bonus for unarmed, melee skill counts more
        me.tohit = me.smod("str")+me.skmod("melee")
        me.dmgtype = choice(["bludgeoning", "slashing"])
    me.aggro = melee
    if "spar" in words[0].lower():
        dmg = attack_roll(me, target, sparring=True)
        exp = (dmg*3)+10
    else:
        dmg = attack_roll(me, target)
        exp = min((dmg*3)+10, (getattr(target, "cr", 5)+1)*10)
    if target.hp <= 0:
        exp *= 1.5
    if melee:
        me.gain_xp("melee", exp)
    elif eqtype == "ranged":
        me.gain_xp("marksman", exp)
    elif eqtype == "magic":
        me.gain_xp("sorcery", exp)
    return True


def cmd_write(words, me, target):
    for i in me.items:
        if i.name == "Stone Tablet" and i.note == "":
            i.note = words[1]
            me.p("[n] has written on their tablet.")
            me.get_familiar("Writing", 20)
            return True
    me.p("You don't have anything to write on.")
    return False


def cmd_watch(words, me, target):
    place = me.get_place()
    if isinstance(place, Tribe):
        if me in place.watchmen:
            place.watchmen.remove(me)
            me.p("[n] is no longer on watch.")
        else:
            place.watchmen.append(me)
            d = me.watch_strength()
            me.p(
                "[n] is volunteering for watchman duty. (Their current defense: "+str(d)+")")
    elif place.camp:
        if me in place.camp["watch"]:
            place.camp["watch"].remove(me)
            me.p("[n] is no longer on watch.")
        else:
            place.camp["watch"].append(me)
            d = me.watch_strength()
            me.p(
                "[n] is volunteering for watchman duty. (Their current defense: "+str(d)+")")
    else:
        me.p("Can only go on watch in the den or in a camp.")
        return False
    return True


def cmd_demolish(words, me, target):
    for b in me.tribe.buildings:
        if words[1].lower() == b.lower():
            res = find_building(b)
            if res.get("destructible", True):
                me.tribe.unfinish_building(res)
                me.p("[n] calls for the demolition of "+b +
                     ". The kobolds make short work of it, freeing up the space.")
                return True
            else:
                me.p("The "+b+" cannot be destroyed.")
                return False
    me.p("Building not found. Must type in the exact name of the building (not case sensitive).")
    return False


def cmd_equip(words, me, target):
    me.del_trait("tool_broke")
    if me.has_trait("noarms"):
        me.p("You need at least one hand to equip that...")
        return False
    elif target.twohands and me.has_trait("onearm"):
        me.p("You need two hands to equip that.")
        return False
    if target in me.items:
        if me.equip == target:
            me.p("[n] unequips their "+target.display()+".")
            me.equip = None
        else:
            me.p("[n] equips their "+target.display()+".")
            me.equip = target
        return True
    else:
        me.p("[n] doesn't have that.")
        return False


def cmd_wear(words, me, target):
    if not hasattr(target, "eqslot") and me.worns["body"] == target:
        target.eqslot = "body"
    if target.eqslot and target.eqslot != "none":
        if target in me.worn_items():
            me.p("[n] takes off their "+target.display()+".")
            me.worns[target.eqslot] = None
            if len(me.items) >= me.inv_size:
                me.p("[n] drops the "+target.display()+" on the ground.")
                target.move(me.get_place())
            else:
                target.move(me)
        elif target in me.items:
            if me.worns[target.eqslot]:
                cmd_wear(words, me, me.worns[target.eqslot])
            me.p("[n] puts on their "+target.display()+".")
            me.worns[target.eqslot] = target
            if target in me.items:
                me.items.remove(target)
        return True
    else:
        me.p("That cannot be worn.")
        return False


def cmd_leave(words, me, target):
    if me.party and me.party.owner != me:
        me.p("You cannot leave a den/dungeon if you are in a party in which you are not the leader.")
        return False
    tribe = me.get_place()
    if isinstance(tribe, Tribe):
        if not me.party:
            p = Party(me)
            if me.carry and me.carry.nick:
                p.join(me.carry)
            me.p("You have made a new party.", True)
        me.p("[n] and their party have left the den.")
        if me.party:
            bolds = me.party.members
        else:
            bolds = [me]
        for k in bolds:
            if k in tribe.kobolds:
                tribe.kobolds.remove(k)
            if k in tribe.tavern:
                tribe.tavern.remove(k)
            if k in tribe.watchmen:
                tribe.watchmen.remove(k)
            if k in tribe.kennel:
                tribe.kennel.remove(k)
            if isinstance(k, Kobold):
                if k.carry:
                    if k.carry in tribe.kobolds:
                        tribe.kobolds.remove(k.carry)
                    if k.carry in tribe.watchmen:
                        tribe.watchmen.remove(k.carry)
                    if k.carry in tribe.tavern:
                        tribe.tavern.remove(k.carry)
                action_queue.append(
                    ["delmember", tribe.get_chan(), k.d_user_id])
                action_queue.append(
                    ["delmember", "tribe-"+str(tribe.id)+"-chat", k.d_user_id])
        me.get_place().examine(me)
        if me.party:
            me.party.broadcast(
                me.display()+" and their party have left the den.")
        return True
    else:
        dgn = me.dungeon
        if dgn and "Dungeon Exit" in tribe.special:
            me.p("[n] and their party emerge from the " +
                 dungeon_data[dgn.d]["name"]+".")
            for k in me.party.k_members:
                k.dungeon = None
                (k.x, k.y, k.z) = (dgn.x, dgn.y, dgn.z)
            me.get_place().examine(me)
            me.broadcast("[n] and their party emerge from the " +
                         dungeon_data[dgn.d]["name"]+".")
            return True
        else:
            me.p("There's nowhere to leave to from here.")
    return False


def cmd_enter(words, me, target):
    p = me.get_place()
    tribe = p.get_tribe()
    if tribe:
        if me.tribe == tribe or (tribe.has_building("Tavern") and tribe.tavern_open):
            for k in me.party.k_members:
                if k.tribe != tribe and k not in tribe.prison and not tribe.has_building("Tavern"):
                    me.p(k.display(
                    )+" is not a member of this tribe. You cannot enter with them in your party.")
                    return False
                if k.id in tribe.banned:
                    me.p(k.display()+" is banned from this tavern and cannot enter.")
                    return False
            if me.party:
                me.party.broadcast(
                    me.display()+" and their party have entered the den.")
            for k in me.party.k_members:
                if k.tribe != tribe and k not in tribe.prison:
                    tribe.tavern.append(k)
                else:
                    tribe.add_bold(k)
                if k.nick:
                    action_queue.append(
                        ["addmember", tribe.get_chan(), k.d_user_id])
                    action_queue.append(
                        ["addmember", "tribe-"+str(tribe.id)+"-chat", k.d_user_id])
                if k.carry:
                    if k.carry.tribe != tribe:
                        tribe.tavern.append(k.carry)
                    else:
                        tribe.add_bold(k.carry)
            for c in me.party.c_members:
                if tribe.has_building("Kennel") and c not in tribe.kennel:
                    tribe.kennel.append(c)
                else:
                    me.p(c.display()+" will have to stay outside.")
            game_print(me.display()+" and their party have arrived.",
                       tribe.get_chan())
            return True
        else:
            if tribe.has_building("Tavern") and not tribe.tavern_open:
                me.p(
                    "[n] discovers that the gates are locked and the tavern is closed... so they knock.")
            else:
                me.p(
                    "[n] discovers that the gates are locked and there is no tavern... so they knock.")
            game_print(
                "There's a knock at the gates. Someone is right outside...", tribe.get_chan())
    else:
        dgn = p.get_dungeon()
        if not dgn:
            me.p("There's nothing to enter.")
        else:
            if dungeon_data[dgn.d].get("faction", None):
                if me.tribe and me.tribe.shc_faction[dungeon_data[dgn.d]["faction"]] < 1:
                    me.tribe.violate_truce(me, dungeon_data[dgn.d]["faction"])
            me.p("[n] and their party embark into the " +
                 dungeon_data[dgn.d]["name"]+".")
            me.broadcast("[n] and their party embark into the " +
                         dungeon_data[dgn.d]["name"]+".")
            for k in me.party.members:
                k.dungeon = dgn
                (k.x, k.y, k.z) = dgn.entry
            me.get_place().examine(me)
            console_print("Entering dungeon at "+str((me.x, me.y, me.z)))
            for m in dgn.map:
                for e in me.world.encounters:
                    if e.place == dgn.map[m]:
                        console_print("Found dungeon encounter at " +
                                      str((dgn.map[m].x, dgn.map[m].y, dgn.map[m].z)))
    return False


def check_move(words, me, cost):
    (newx, newy, newz) = (me.x, me.y, me.z)
    p = me.get_place()
    if words[1] == "north":
        newy -= 1
    elif words[1] == "west":
        newx -= 1
    elif words[1] == "east":
        newx += 1
    elif words[1] == "south":
        newy += 1
    elif words[1] == "up":
        newz -= 1
        if "Stairs Up" not in p.special:
            me.p("Can't go up here.")
            return None
    elif words[1] == "down":
        newz += 1
        if "Stairs Down" not in p.special:
            me.p("Can't go down here.")
            return None
    else:
        me.p("That is not a valid direction.")
        return None
    if me.dungeon:
        t = me.dungeon.get_tile(newx, newy, newz)
    else:
        t = me.world.get_tile(newx, newy, newz)
    clear = "good"
    if words[1] not in ["up", "down"] and p.blocked[words[1][0]]:
        clear = "That way is blocked."
    for k in me.party.k_members:
        mcost = cost
        for t in k.traits:
            mcost += trait_data[t].get("move_ap", 0)
        if k.ap < mcost and not k.has_trait("carried"):
            clear = k.display()+" does not have the AP to move."
    for c in me.party.c_members:
        if not c.carry:
            continue
        mcost = cost
        if c.carry.ap < mcost:
            clear = c.carry.display()+" does not have the AP to move."
    if clear != "good":
        me.p(clear)
        return None
    return (newx, newy, newz)


def spell_retreat(spell, words, me, target):
    if words[2] in DIR_FULL:
        words[2] = DIR_FULL[words[2]]
    move = check_move(["move", words[2]], me, 0)
    party = me.party  # in case the leader dies in the escape
    cost = len(party.members)
    if not move:
        return False
    if me.mp_tax(cost):
        for e in me.world.encounters:
            if me.party in e.engaged:
                e.disengage(me.party)
                break
        me.p("[n]'s party flees "+words[1]+".")
        party.move(move[0], move[1], move[2], 0)
        return True
    return False


def cmd_flee(words, me, target):
    if words[1] in DIR_FULL:
        words[1] = DIR_FULL[words[1]]
    move = check_move(words, me, 2)
    party = me.party  # in case the leader dies in the escape
    if not move:
        return False
    for e in me.world.encounters:
        if me.party in e.engaged:
            e.disengage(me.party)
            break
    ao = []
    for c in e.creatures:
        for t in c.traits:
            if not trait_data[t].get("turn_block", False):
                ao.append(c)
    for k in me.party.members:
        if chance(25) and len(ao) > 0:
            c = choice(ao)
            ao.remove(c)
            k.p(c.name+" takes an attack of opportunity against [n]!")
            c.attack(k)
        elif chance(25):
            drop = choice(k.items)
            if drop:
                drop.move(k.get_place())
                k.p("[n] drops the "+drop.display() +
                    " in their rush to escape.")
    me.p("[n]'s party flees "+words[1]+".")
    party.move(move[0], move[1], move[2], 2)
    return True


def cmd_move(words, me, cost):
    if words[1] in DIR_FULL:
        words[1] = DIR_FULL[words[1]]
    elif words[1] == "u":
        words[1] = "up"
    elif words[1] == "d":
        words[1] = "down"
    p = me.get_place()
    if me.dungeon:
        cost = 0
    else:
        cost = 1
    move = check_move(words, me, cost)
    if not move:
        return False
    me.p("[n]'s party moves "+words[1]+".")
    me.party.move(move[0], move[1], move[2], cost)
    return True


def cmd_prospect(words, me, target):
    t = me.world.get_tile(me.x, me.y, me.z)
    if me.z > 0 or me.dungeon:
        prospower = droll(1, 20)+me.smod("int") + \
            me.smod("wis")+me.skmod("geology")
        exp = 10
        found = []
        anyres = False
        console_print(me.get_name()+" prospower is "+str(prospower) +
                      ", base is "+str(me.smod("int")+me.smod("wis")+me.skmod("geology")))
        for d in t.resources:
            console_print("checking for, " +
                          str(t.resources[d])+", "+str(abs(t.mined[d])))
            if t.mined[d]+math.floor(prospower/5) > 0:
                if t.mined[d] < 0:
                    deep = ", "+str(abs(t.mined[d]))+" layers deep"
                else:
                    deep = ", exposed"
                if t.resources[d]:
                    found.append(t.resources[d]+" ("+DIR_FULL[d]+deep+")")
                exp += min(t.mined[d], 0)*-5
            elif t.resources[d]:
                found.append("Unknown ("+DIR_FULL[d]+", ??? layers deep)")
            if t.resources[d]:
                anyres = True
        if len(found) > 0:
            me.p(
                "[n] prospects the zone and finds the following materials available: "+"; ".join(found))
        elif anyres:
            me.p(
                "[n] prospects the zone and finds traces of unknown minerals, but fails to identify them.")
        else:
            me.p("[n] prospects the zone and finds nothing interesting.")
        if t.stability >= 100:
            stable = "stable."
        elif t.stability > 80:
            stable = "a little unstable."
        elif t.stability > 50:
            stable = "very unstable."
        else:
            stable = "crumbling as we speak."
        me.p("The cavern in this area appears to be "+stable)
        me.gain_xp("geology", exp)
    else:
        me.p("There is nothing to prospect here.")
    return True


def cmd_butcher(words, me, target):
    me.equip_best("butchering")
    if target.type != "corpse":
        me.p("Must butcher a corpse.")
    else:
        cost = target.size
        half = False
        p = me.get_place()
        if (isinstance(p, Tribe) and "Butcher Table" in p.buildings) or target.name == "Skeleton":
            cost = math.floor(cost/2)
            if target.size % 2 == 1:
                half = True
                if me.movement+50 >= 100:
                    cost += 1
        if me.ap_tax(cost):
            if half:
                me.movement += 50
                me.movement = me.movement % 100
            hit = target.butcher(me)
            me.gain_xp("survival", (hit*2)+10)
            return True
    return False


def forage(me, lm=None, dgn=None, mm=None):
    forages = {}
    amounts = {}
    wt = 0
    mwt = 0
    exp = 0
    if mm:
        z = mm.z
    else:
        z = me.z
    if dgn:  # must be dungeon
        for i in dungeon_data[dgn.d]["forage"]:
            forages[i[0]] = i[3]
            amounts[i[0]] = [i[1], i[2]]
            wt += i[3]
            if i[3] > mwt:
                mwt = i[3]
    elif lm in landmark_data and chance(landmark_data[lm].get("foragechance", 0)):
        for i in landmark_data[lm]["forage"]:
            forages[i[0]] = i[3]
            amounts[i[0]] = [i[1], i[2]]
            wt += i[3]
            if i[3] > mwt:
                mwt = i[3]
    else:
        for i in item_data:
            if i.get("forage", None):
                if z >= i["forage"]["level"][0] and (i["forage"]["level"][1] == -1 or z <= i["forage"]["level"][1]):
                    forages[i["name"]] = i["forage"]["weight"]
                    amounts[i["name"]] = i["forage"].get("amount", [1, 1])
                    wt += i["forage"]["weight"]
                    if i["forage"]["weight"] > mwt:
                        mwt = i["forage"]["weight"]
    found = random.randint(1, wt)
    item = None
    for f in forages:
        if found < forages[f]:
            am = random.randint(amounts[f][0], amounts[f][1])
            item = spawn_item(f, me, am)
            if isinstance(me, Kobold) or mm:
                if am > 1:
                    me.p("[n] has found: "+item.name+" x"+str(am))
                else:
                    me.p("[n] has found: "+item.name)
            exp = mwt-forages[f]+5
            break
        else:
            found -= forages[f]
    if not item:
        item = spawn_item("Kobold Egg", me)
        if isinstance(me, Kobold):
            me.p("[n] has found an abandoned Kobold Egg! How'd this get here?")
        exp += 50
    return exp


def cmd_searchall(words, me, target):
    for k in me.party.k_members:
        if k.age < 1:
            continue
        if k.has_trait("bound") and not k.has_trait("broken"):
            continue
        if k == me or not k.nick or k.orders:
            cmd_search(words, k, target)
    for c in me.party.c_members:
        if "search" in c.training:
            cmd_search(words, c, target)
    return True


def cmd_search(words, me, target):
    t = me.get_place()
    if isinstance(t, Tribe) or t.get_tribe():
        me.p("There is nothing to find at the den, besides what's in storage.")
        return False
    if isinstance(me, Creature):
        mm = me.party.owner
        c = ",".join([str(mm.x), str(mm.y), str(mm.z)])
        surv = me.smod("wis")+5
    else:
        mm = None
        c = ",".join([str(me.x), str(me.y), str(me.z)])
        surv = me.smod("wis")+me.skmod("survival")
    if c in me.searched:
        me.p("[n] has already searched here today.")
        return False
    roll = random.randint(1, 20)+surv
    exp = 5
    if roll > 10:
        spec = choice(t.special)
        exp += forage(me, lm=spec, mm=mm)
    else:
        me.p("[n]'s search has turned up nothing.")
    if not mm:
        if chance(surv):
            tracks = None
            if chance(50):
                ct = me.world.find_tile_feature(surv+5, t, None, "factionbase")
                if ct:
                    for l in ct.special:
                        if landmark_data[l].get("faction", None):
                            tracks = landmark_data[l]["faction"]
            else:
                ct = None
                dist = 999
                for t in me.world.tribes:
                    if t.z == me.z and abs(t.x-me.x) < surv+5 and abs(t.y-me.y) < surv+5 and me.tribe != t:
                        d = get_tri_distance(me.x, t.x, me.y, t.y)
                        if d < dist:
                            dist = d
                            ct = t
                tracks = "Kobold"
            if ct and tracks:
                dir = get_dir(ct, me)
                if dir != "same":
                    me.p("[n] finds what appear to be " +
                         tracks+" tracks leading "+dir+".")
                exp += 20
        me.gain_xp("survival", exp)
    me.searched.append(c)
    return True


def cmd_fortify(words, me, target):
    t = me.get_place()
    if isinstance(t, Tribe) or t.get_tribe() or not t.camp:
        me.p("Must be in a camp.")
        return False
    if not me.has_item("*block"):
        me.p("You need any kind of block or brick to fortify the camp.")
        return False
    me.consume_item("*block")
    t.camp["defense"] += 5
    me.p("[n] has fortified the camp and added 5 defense to it.")
    return True


def cmd_hide(words, me, target):
    t = me.get_place()
    if t.camp:
        me.p("There's no need to hide at a camp.")
        return False
    stealth = droll(1, 20)+me.stealth
    for l in t.special:
        stealth += landmark_data[l].get("stealth_bonus", 0)
    if t.get_tribe():
        stealth -= 5
    stealth -= 5*len(me.party.members)
    me.hiding = max(10, me.hiding-max(5, stealth))
    me.p("[n] looks for a good hiding place to wait out the raid. They estimate that their survival chances are about "+str(100-me.hiding)+"%.")
    me.gain_xp("stealth", 10)
    return True


def spell_hut(spell, words, me, target):
    t = me.get_place()
    if isinstance(t, Tribe) or t.get_tribe():
        me.p("Can't make camp on a tile containing a tribe's den.")
        return False
    if t.camp:
        me.p("There's already a camp here.")
        return False
    for l in t.special:
        if landmark_data[l].get("spawns", None):
            me.p("It's too dangerous to set up camp at the "+l+".")
            return False
    me.p("[n] waves their hands around the party, and a hut of magical force materializes around them.")
    t.camp = {"tribe": me.tribe, "heat": 0,
              "defense": 0, "watch": [], "magic": true}
    return True


def cmd_camp(words, me, target):
    t = me.get_place()
    if isinstance(t, Tribe) or t.get_tribe():
        me.p("Can't make camp on a tile containing a tribe's den.")
        return False
    if not me.has_item("*block", 2):
        me.p("You need 2 Stone Blocks to make a camp.")
        return False
    if t.camp:
        me.p("There's already a camp here.")
        return False
    for l in t.special:
        if landmark_data[l].get("spawns", None):
            me.p("It's too dangerous to set up camp at the "+l+".")
            return False
    me.consume_item("*block", 2)
    me.p("[n] puts up some rudimentary fortifications and sets up camp.")
    stealth = 0
    for k in me.party.k_members:
        stealth += random.randint(1, 20)+k.stealth
    stealth = int(stealth/len(me.party.k_members))
    if me.tribe:
        th = me.tribe.heat_faction["Goblin"]
    else:
        th = 20
    heat = int(th*(20-stealth)/100)
    if stealth >= 20:
        me.p("The camp is nigh-undetectable from outside. Well done.")
        heat = 0
        stealth *= 2
    else:
        me.p("[n]'s party contributes to making the camp as inconspicuous as possible. They estimate that it has about " +
             str(heat)+" heat right now.")
    t.camp = {"tribe": me.tribe, "heat": heat, "defense": 0, "watch": []}
    for k in me.party.k_members:
        k.gain_xp("stealth", stealth*3)
    return True


def cmd_attune(words, me, target):
    if target.school == "none" or target.type == "gem":
        me.p(target.display()+" cannot be attuned.")
        return False
    gem = find_item(words[2], me, type="gem")
    if not gem:
        me.p("Gem '"+words[2]+"' not found.")
        return False
    if target.school != gem.school and target.school != "open":
        al = 1
    else:
        al = target.attunelevel+1
    if not me.has_item(gem.name, al):
        me.p("Not enough "+gem.name+" for attunement level " +
             str(al)+". (Need "+str(al)+")")
    elif me.mp_tax(al*2):
        me.consume_item(gem.name, al)
        target.attunelevel = al
        target.school = gem.school
        me.p("[n] has attuned the "+target.display() +
             " to "+target.school+" level "+str(al)+".")
        me.gain_xp("arcana", al*20)
        return True
    return False


async def cmd_use(words, me, chan):
    target = await multi_select(chan, words[1], me, landmarks=True)
    if not target:
        return False
    if isinstance(target, Item):
        if target.hp < 0:
            user = discord.utils.get(guild.members, id=me.d_user_id)
            conf = await confirm_prompt(chan, "This item is dangerous; it will cost HP to use. Do you wish to proceed?", user)
            if not conf:
                return False
        return target.use(me)
    else:
        if target == "Hot Spring" or target == "Artificial Hot Spring":
            if me.ap_tax(1):
                if me.has_trait("stressed"):
                    me.del_trait("stressed")
                    me.p("[n]'s stress ebbs away...")
                if not me.has_trait("relaxed"):
                    me.add_trait("relaxed")
            else:
                return False
        else:
            me.p("You can't use the "+target+" in any meaningful way.")
            return False
        return True


def cmd_expand(words, me, target):
    p = me.get_place()
    tribe = None
    if isinstance(p, Tribe):
        tribe = p
        p = me.world.get_tile(me.x, me.y, me.z)
    if p.farm_cap <= 0:
        me.p("There's nothing to expand here.")
        return False
    elif p.farm_cap >= 1000:
        me.p("The farm is already as big as it can get in this tile.")
        return False
    for l in p.special:
        if "Farm" in l:
            break
    me.equip_best("construction")
    prog = (me.smod("str")+(me.skmod("construction")*3))+10
    prog += me.equip_bonus("construction")
    sp = math.floor((p.farm_cap+prog)/100)-math.floor(p.farm_cap/100)
    if tribe and sp > 0:
        if tribe.space < sp:
            me.p("There's no space to expand the farm.")
            return False
        tribe.space -= sp
        me.p("[n] uses "+str(sp)+" space to expand the farm.")
    p.farm_cap += prog
    if p.farm_cap >= 1000:
        p.farm_cap = 1000
    me.p("[n] has added "+str(prog)+" capacity to the " +
         l+". ("+str(p.farm_cap)+"/1000)")
    exp = prog
    me.gain_xp("construction", exp)
    if me.accident(10-me.smod("dex")):
        me.p("[n] clumsily injured themselves!")
    return True


def cmd_repair(words, me, target):
    me.equip_best("construction")
    res = find_building(words[1], True)
    b = res["name"]
    p = me.get_place()
    if b in p.building_health and p.building_health[b] < 100:
        prog = (me.smod("str")+(me.skmod("construction")*3))+10
        prog += me.equip_bonus("construction")
        prog = math.ceil(prog/2)
        prog = math.ceil(prog*100/res["work"])
        prog = max(1, prog)
        p.building_health[b] += prog
        me.p("[n] repairs "+str(prog)+"% of the "+b+".")
        if p.building_health[b] >= 100:
            me.p("The "+b+" is fully repaired!")
            del p.building_health[b]
        me.gain_xp("construction", prog)
        if me.accident(10-me.smod("dex")):
            me.p("[n] clumsily injured themselves!")
        return True
    else:
        me.p("No building called '"+words[1]+"' needs repair.")
    return False


def cmd_build(words, me, target):
    if not me.tribe and not me.has_trait("bound"):
        me.p("You can't build things if you aren't in a tribe (for now)")
        return False
    me.equip_best("construction")
    res = find_building(words[1], True)
    p = me.get_place()
    tile = me.world.get_tile(me.x, me.y, me.z)
    if isinstance(p, Tribe):
        intribe = True
    else:
        intribe = False
    if res:
        if not intribe and not res.get("landmark", False):
            me.p("Can't build that in the overworld.")
            return False
        good = check_req(p, res.get("req", []), me)
        g = []
        for m in res.get("materials", []):
            gra = m.split("/")
            g.append(m)
            for b in gra:
                arg = b.split(":")
                if len(arg) == 1:
                    arg.append(1)
                if p.has_item(arg[0], int(arg[1])):
                    g.remove(m)
                    break
        if len(g) > 0:
            good = "Missing material(s): "+", ".join(g)
        if res.get("farm", False):
            for l in tile.special:
                if landmark_data[l].get("farm", False):
                    good = "Already have a farm on this tile."
        if good != "good":
            me.p("Cannot build "+res["name"]+". "+good)
            if isinstance(p, Tribe):
                p.justbuilt = res["name"]
            return False
        elif res.get("landmark", False):
            if res["name"] not in tile.special or res.get("repeatable", False):
                tile.do_building(me, res)
            else:
                me.p("That has already been built here.")
                return False
        elif not res.get("repeatable", False) and res["name"] in p.buildings:
            me.p("That has already been built.")
            return False
        else:
            p.do_building(me, res)
        if me.accident(10-me.smod("dex")):
            me.p("[n] clumsily injured themselves!")
        return True
    else:
        me.p("Can't find available building project called '"+words[1]+"'")
    return False


def cmd_research(words, me, target):
    res = find_research(words[1])
    p = me.get_place()  # must be a tribe
    if res and res["name"] in p.get_available_research():
        p.do_research(me, res)
        return True
    else:
        me.p("Can't find available research called '"+words[1]+"'")
        p.justbuilt = words[1]
    return False


def cmd_recycle(words, me, target):
    if len(target.recycle["into"]) <= 0:
        me.p("That cannot be recycled.")
        return False
    good = check_req(me.tribe, target.recycle["req"], me)
    if good != "good":
        me.p("[n] cannot recycle "+target.display()+": "+good)
        return False
    base = target.recycle["chance"]
    base += (me.smod("dex")+me.skmod("crafting"))*2
    base += 5*target.quality
    if target.base_durability > 0:
        base *= target.durability/target.max_durability
    reclaim = []
    for i in target.recycle["into"]:
        if chance(base):
            rc = spawn_item(i, me)
            reclaim.append(i)
    if len(reclaim) > 0:
        me.p("[n] recycles the "+target.name +
             " and reclaims: "+", ".join(reclaim)+".")
    else:
        me.p("[n] tries to recycle the "+target.name +
             ", but gets nothing usable out of it.")
    target.destroy("Recycled")
    me.gain_xp("crafting", (len(reclaim)+1)*10)
    return True


def cmd_craft(words, me, target):
    cattest = words[1].split()
    catspecs = {}
    for w in cattest:
        if "=" in w:
            st = w.split("=")
            catspecs[st[0].replace("*", "")] = st[1].replace("_", " ")
            me.p("Attempting to use "+st[1] +
                 " for "+st[0]+"-category ingredient")
            words[1] = words[1].replace(" "+w, "")
    catspecneeds = list(catspecs.keys())
    c = find_craft(words[1])
    place = me.get_place()
    if c:
        good = check_req(place, c.get("req", []), me)
        if c.get("liquid", False):
            container = None
            for i in me.items+me.get_place().items:
                if i.type == "container" and i.liquid == c["result"] and i.liquid_units+c.get("amount", 1) <= i.liquid_capacity:
                    container = i
                    break
            if not container:
                for i in me.items+me.get_place().items:
                    if i.type == "container" and not i.liquid and i.liquid_units+c.get("amount", 1) <= i.liquid_capacity:
                        container = i
            if not container:
                good = "No suitable container to store result"
        needs = list(c["materials"])
        containers = []
        using = []
        for n in c["materials"]:
            alts = n.split("/")
            for b in alts:
                a = b.split(":")
                if len(a) == 1:
                    a.append(1)
                am = int(a[1])
                if a[0][0] == "*":
                    cat = a[0].replace("*", "")
                else:
                    cat = None
                if cat in catspecneeds:
                    catspecneeds.remove(cat)
                if a[0] == "Water" and isinstance(place, Tribe) and place.has_building("Well") and place.water >= am:
                    containers.append(["Well", am])
                    needs.remove(n)
                    break
                for i in me.items+place.items:
                    if i.type == "bait":
                        continue
                    if (cat and i.name in item_cats[cat]) or (not cat and i.name == a[0]):
                        if cat and cat in catspecs and catspecs[cat] not in i.name.lower():
                            continue
                        using.append([i, min(am, i.num)])
                        am = max(am-i.num, 0)
                        if am <= 0:
                            needs.remove(n)
                            break
                    elif i.liquid and i.liquid == a[0]:
                        containers.append([i, min(am, i.liquid_units)])
                        am = max(am-i.liquid_units, 0)
                        if am <= 0:
                            needs.remove(n)
                            break
                if n not in needs:
                    break
        if len(needs) > 0:
            good = "Missing required materials: "+", ".join(needs)
        if len(catspecneeds) > 0:
            good = "Category not used: "+", ".join(catspecneeds)
        if good == "good":
            if c.get("mana", 0) > 0:
                ready = me.mp_tax(c["mana"])
            else:
                cost = c["work"]
                if c.get("blast_processing", False) and isinstance(place, Tribe) and place.has_building("Blast Furnace"):
                    cost -= 1
                ready = me.ap_tax(cost)
            if ready:
                sk = c.get("skill", "crafting")
                qtotal = 0
                qnum = 0
                for u in using:
                    u[0].num -= u[1]
                    qtotal += u[0].quality
                    qnum += 1
                    if u[0].num <= 0:
                        u[0].destroy("Used in crafting")
                for u in containers:
                    if u[0] == "Well":
                        place.water -= u[1]
                    else:
                        u[0].liquid_units -= u[1]
                        if u[0].liquid_units <= 0:
                            u[0].liquid = None
                if qnum > 0:
                    qav = int(qtotal/qnum)
                else:
                    qav = 0
                prof = (me.smod(skill_data[sk]["stat"])+me.skmod(sk))*2
                fmulti = 1
                for r in c.get("req", []):
                    if r[0] == "tool":
                        for i in me.items:
                            if i.tool == r[1]:
                                i.lower_durability()
                                break
                    if r[0] == "research":
                        f = me.familiar(r[1])
                        if f == 0:
                            fmulti *= 0.6
                        elif f == 1:
                            fmulti *= 0.8
                roll = int((random.randint(1, 20)+prof+qav)*fmulti)
                console_print("Crafting roll before tool bonus: "+str(roll))
                if c.get("tool", None):
                    me.equip_best(c["tool"])
                    if me.equip and me.equip.tool == c["tool"]:
                        roll += me.equip.toolpower
                    roll = max(me.equip_bonus(c["tool"]), roll)
                    console_print("Crafting roll after tool bonus: "+str(roll))
                q = math.floor(roll/5)-5
                am = c.get("amount", 1)
                if not c.get("ignore_quality", False) and am != 1:
                    am += q
                am = max(1, am)  # can't craft 0 of an item
                if c.get("liquid", False):
                    container.liquid = c["result"]
                    container.liquid_units += c.get("amount", 1)
                    amstr = "some"
                else:
                    newcraft = spawn_item(c["result"], me.get_place(), am)
                    if not c.get("ignore_quality", False) and am == 1:
                        newcraft.set_quality(q)
                    if am > 1:
                        amstr = str(am)+"x"
                    else:
                        amstr = "a"
                me.p("[n] has successfully crafted "+amstr+" " +
                     get_q_desc(q)+"-quality "+c["result"]+".")
                if c.get("mana", 0) > 0:
                    exp = int((max(2, q+5)/2)*10*c["mana"])
                else:
                    exp = int((max(2, q+5)/2)*10*c["work"])
                me.gain_xp(sk, exp)
                me.gain_fam(c.get("req", []), exp)
                return True
        else:
            me.p("[n] cannot craft "+c["result"]+". "+good)
    else:
        me.p("No craft found called "+words[1])
    if isinstance(place, Tribe):
        place.justbuilt = words[1]
    return False


def cmd_breed(words, me, k):
    good = False
    if k.nick:
        if k.id in me.breeders:
            good = True
        else:
            if me.id not in k.breeders:
                k.breeders.append(me.id)
                me.p("[n] has requested to breed with "+k.display()+". " +
                     k.get_name()+" should type !breed "+me.get_name()+" to accept.")
            else:
                me.p("You have already requested a breeding session with that kobold.")
    elif k.age < 6:
        me.p(k.display()+" is not old enough for this.")
    elif k.tribe and k.tribe == me.tribe:
        good = True
    else:
        me.p(k.display() +
             " does not know [n] well enough to want to breed with them.")
    if good:
        if me.ap < 2 or k.ap < 2:
            me.p("[n] wants to breed with "+k.display() +
                 " but they don't both have 2 AP to spare.")
        elif me.has_trait("breed"):
            me.p("[n] has already made a breeding attempt this month.")
        elif k.has_trait("breed"):
            k.p("[n] has already made a breeding attempt this month.")
        else:
            me.ap_tax(2)
            k.ap_tax(2)
            if len(words) > 2 and words[2].lower() in ["restrain", "restraint", "pullout", "careful", "nobaby", "noeggs", "noegg", "nobabies"]:
                pullout = True
            else:
                pullout = False
            me.breed(k, pullout=pullout)
            for p in [me, k]:
                if p.has_trait("stressed") and p.save("wis") >= 12:
                    p.del_trait("stressed")
                    p.p("[n] is feeling a lot more relaxed after that.")
            if me.id in k.breeders:
                k.breeders.remove(me.id)
            if k.id in me.breeders:
                me.breeders.remove(k.id)
            return True
    return False


def cmd_roll(words, me, target):
    m = 0
    if len(words) > 1:
        args = words[1].lower().split()
        for a in args:
            if a in ["str", "dex", "con", "int", "wis", "cha"]:
                m += me.smod(a)
            elif "+" in a:
                try:
                    m += int(a.replace("+", ""))
                except:
                    me.p("'"+a+"' is not a number.")
                    return False
            elif "-" in a:
                try:
                    m -= int(a.replace("-", ""))
                except:
                    me.p("'"+a+"' is not a number.")
                    return False
            else:
                me.p("'"+a+"' is not a valid argument.")
                return False
    roll = droll(1, 20)
    if roll == 20:
        rstr = "**20**"
    elif roll == 1:
        rstr = "~~1~~"
    else:
        rstr = str(roll)
    if m >= 0:
        mstr = "+"+str(m)
    else:
        mstr = str(m)
    me.p("[n] rolls a d20 and gets "+str(roll+m)+" ("+rstr+mstr+").")
    return True


def cmd_train2(words, me, k):
    sk = None
    for s in skill_data:
        if words[1].lower() in s:
            sk = s
    if not sk:
        me.p("Skill '"+words[1]+"' not found.")
        return False
    train = None
    place = me.get_place()
    for b in place.buildings:
        build = find_building(b)
        if sk in build.get("enable_training", []) and place.has_building(b):
            train = build
    if not train:
        me.p("No building available that can train " +
             skill_data[sk]["name"]+".")
        return False
    mana = False
    if skill_data[sk].get("magic", False):
        mana = True
        if me.mp < 1:
            me.p("Not enough mana. (need 1, have "+str(me.mp)+")")
            return False
    else:
        if me.ap < 1:
            me.p("Not enough AP. (need 1, have "+str(me.ap)+")")
            return False
    if mana:
        me.mp_tax(1)
    else:
        me.ap_tax(1)
    me.p("[n] spends some time training their " +
         skill_data[sk]["name"]+" skill.")
    exp = 15
    if me.accident(10):
        me.p("[n] pushes themselves a little too hard.")
        exp += 15
    if chance(10):
        me.p("The "+train["name"]+" suffers some wear and tear.")
        place.building_damage(train["name"], droll(1, 10))
    me.gain_xp(sk, exp)
    return True


def cmd_spar(words, me, k):
    good = False
    if k.nick:
        if k.id in me.spartners:
            good = True
        else:
            if me.id not in k.spartners:
                k.spartners.append(me.id)
                me.p("[n] has requested to spar with "+k.display()+". " +
                     k.get_name()+" should type !spar "+me.get_name()+" to accept.")
            else:
                me.p("You have already requested a sparring session with that kobold.")
    elif k.age < 6:
        me.p(k.display()+" is not old enough for this.")
    elif k.tribe and k.tribe == me.tribe:
        good = True
    else:
        me.p(k.display()+" is not interested in sparring with [n].")
    if good:
        if me.ap < 1 or k.ap < 1:
            me.p("[n] wants to spar with "+k.display() +
                 " but they don't both have 1 AP to spare.")
        else:
            me.ap_tax(1)
            k.ap_tax(1)
            cmd_attack(words, me, k)
            cmd_attack(words, k, me)
            return True
    return False


def cmd_tribe(words, me, target):
    try:
        k = find_kobold(words[2], me.get_place(), me.world)
    except:
        k = None
    cmds = ["new", "join", "leave", "invite"]
    if len(words) < 2 or words[1] not in cmds:
        me.p("Possible actions:Actions:\nnew - Create a new tribe, if you have none. Must be at a camp.\nleave - Leave your current tribe. You will no longer be able to enter their den.\ninvite - Invite <kobold> to your tribe (Chieftain only). A nameless kobold cannot switch tribes this way.\njoin - Join <kobold>'s tribe, if you have been invited.")
    elif words[1] == "new":
        if not me.has_trait("tribe_join"):
            if me.party and me.party.owner == me:
                if not me.tribe:
                    if me.get_place().camp:
                        for k in me.world.kobold_list:
                            if (k.x, k.y, k.z) == (me.x, me.y, me.z) and k.tribe and k.party != me.party:
                                me.p(
                                    "Can't make a tribe: A kobold from another tribe is occupying this camp ("+k.display()+").")
                                return False
                        me.tribe = Tribe(me.world, me.x, me.y, me.z)
                        me.world.tribes.append(me.tribe)
                        for k in me.party.k_members:  # the earlier world check returns if there are party members in other tribes so this should be fine
                            k.tribe = me.tribe
                        me.p(
                            "[n] tidies up the camp here to make it more homey. With that, it has been converted into a den.")
                        me.tribe.chieftain = me
                        action_queue.append(
                            ["addrole", "Chieftain", me.d_user_id])
                        me.p("[n] has founded a new tribe with their party!")
                        me.tribe.heat_faction["Goblin"] = me.get_place(
                        ).camp["heat"]
                        me.get_place().camp = {}
                        me.add_trait("tribe_join")
                        me.cp = me.max_cp
                        return True
                    else:
                        me.p("Can't make a tribe: You must be on a tile with a camp.")
                else:
                    me.p("You already have a tribe.")
            else:
                me.p("Only a party leader can start a new tribe.")
        else:
            me.p("You have joined a tribe too recently.")
    elif words[1] == "join":
        if not me.has_trait("tribe_join"):
            if not me.tribe:
                if k and k.tribe and k.tribe.chieftain == k:
                    if me.id in k.tribe.invites:
                        k.tribe.invites.remove(me.id)
                        me.tribe = k.tribe
                        me.p("[n] has devoted themselves to "+k.display() +
                             "'s tribe and is now an official member.")
                        me.add_trait("tribe_join")
                        if me in me.tribe.tavern:
                            me.tribe.tavern.remove(me)
                            me.tribe.add_bold(me)
                        return True
                    else:
                        me.p("You have not been invited to this tribe.")
                else:
                    me.p("You must select a kobold who is the chieftain of a tribe.")
            else:
                me.p("You must leave your tribe before you can join another one.")
        else:
            me.p("You have joined a tribe too recently.")
    elif words[1] == "leave":
        if me.tribe:
            if not me.has_trait("tribe_leave"):
                if me.tribe.chieftain == me:
                    me.tribe.chieftain = None
                    action_queue.append(["delrole", "Chieftain", me.d_user_id])
                if me.tribe.overseer == me:
                    me.tribe.overseer = None
                me.tribe = None
                me.p("[n] has officially left their tribe.")
                me.add_trait("tribe_leave")
                return True
            else:
                me.p("You have left a tribe too recently.")
        else:
            me.p("You are not in a tribe.")
    elif words[1] == "invite":
        if me.tribe:
            if me.tribe.chieftain == me:
                if k:
                    if not k.tribe:
                        if k.nick:
                            me.tribe.invites.append(k.id)
                            me.p("[n] has invited "+k.display()+" to their tribe. " +
                                 k.display()+" can now join with `!tribe join "+me.get_name()+"`.")
                            me.broadcast(me.display()+" has invited "+k.display()+" to their tribe. " +
                                         k.display()+" can now join with `!tribe join "+me.get_name()+"`.")
                            exed = get_pdata(k.d_user_id, "exiled_from", [])
                            if me.tribe.id in exed:
                                exed.remove(me.tribe.id)
                            return True
                        else:
                            me.p(
                                "Can't invite a nameless kobold in this way. You must use `!recruit`.")
                    else:
                        me.p(
                            "Can't invite a kobold from another tribe; they must leave their own first.")
                else:
                    me.p("Kobold not found. Make sure you spelled their name correctly (not case sensitive), and they're in the same place as you.")
            else:
                me.p("Only the chieftain can invite a kobold to their tribe.")
        else:
            me.p("You don't have a tribe to invite someone into.")
    return False


def cmd_party(words, me, target):
    place = me.get_place()
    try:
        k = find_kobold(words[2], place, me.world)
        if not k:
            k = find_creature_i(words[2], me)
    except:
        k = None
    cmds = ["new", "join", "leave", "members", "invite", "kick", "leader"]
    if len(words) < 2 or words[1] not in cmds:
        me.p("Possible actions:\n`!party new` - Make a new party\n`!party join <name>` - Join <name>'s party (if you were invited)\n`!party invite <name>` - Invite <name> to your party\n`!party members` - Show members of your party\n`!party kick <name>` - Kick <name> out of your party, if you're the leader\n`!party leave` - Leave the party. If you're the leader, a random named kobold will be made the new leader. If there are no eligible members, it will disband.")
    elif words[1] == "new":
        if not me.party:
            p = Party(me)
            if me.carry and me.carry.nick:
                p.join(me.carry)
            me.p("You have made a new party.", True)
            return True
        else:
            me.p("You already have a party.", True)
    elif words[1] == "join":
        if not me.party or place != me.tribe:
            if k and me != k:
                if k.party:
                    if place == k.get_place():
                        if me.id in k.party.invites:
                            if me.party:
                                me.party.leave(me, reform=False)
                            k.party.invites.remove(me.id)
                            k.party.join(me)
                            return True
                        else:
                            me.p("You have not been invited to this party.", True)
                    else:
                        me.p("You can't join a party that isn't in your area.", True)
                else:
                    me.p("That kobold has not formed a party.", True)
            else:
                me.p("You must select a target kobold.", True)
        else:
            me.p("You're already in a party.", True)
    elif words[1] == "leave":
        if not me.party:
            me.p("You do not have a party.")
        else:
            me.party.leave(me)
    elif words[1] == "members":
        if not me.party:
            me.p("You do not have a party.")
        else:
            l = []
            m = []
            for k in me.party.members:
                a = k.display()
                if k == me.party.owner:
                    a += " (Leader)"
                if isinstance(k, Kobold):
                    l.append(a)
                else:
                    m.append(a)
            me.p("Kobolds in your party:\n"+", ".join(l), True)
            if len(m) > 0:
                me.p("Creatures in your party:\n"+", ".join(m), True)
            return True
    elif me.party and me.party.owner != me:
        me.p("You are not the owner of this party.", True)
    elif len(words) < 3:
        me.p("You must select a target kobold.", True)
    elif not k:
        me.p("Kobold not found. Make sure you spelled their name correctly (not case sensitive), and they're in the same place as you.", True)
    elif words[1] == "invite":
        if not me.party:
            p = Party(me)
            if me.carry and me.carry.nick:
                p.join(me.carry)
            me.p("You have made a new party.", True)
        if k.nick and not k.has_trait("inactive") and me != k:
            me.party.invites.append(k.id)
            me.p("You have invited "+k.display()+" to your party.", True)
            me.broadcast(me.display()+" has invited " +
                         k.display()+" to their party.")
            return True
        elif k.party == me.party:
            me.p("That kobold is already in your party.")
        elif k.party and time.time()-k.party.owner.lasttime < 1800:
            me.p("That kobold is already in an active party. (A party is considered inactive if its owner hasn't submitted a command in 30 minutes.)", True)
        elif isinstance(k, Kobold) and (k.tribe != me.tribe or not k.tribe) and k not in me.tribe.prison:
            me.p("You can't add a kobold from another tribe to your party.", True)
        elif isinstance(k, Creature) or k.age > 0:
            if k.party:
                k.party.leave(k)
            me.party.join(k)
        else:
            me.p("That kobold is too young to travel.", True)
    elif not me.party:
        me.p("You do not have a party.")
    elif k not in me.party.members:
        me.p(k.display()+" is not in your party.", True)
    elif words[1] == "kick":
        if isinstance(k, Creature):
            if isinstance(place, Tribe):
                if not place.has_building("Kennel"):
                    me.p("The creature needs a kennel to stay in the den unattended.")
                    return False
            elif "Pasture" not in place.special:
                me.p("The creature needs a pasture to stay in the overworld unattended.")
                return False
        game_print(k.display()+" has been kicked from the party.",
                   me.party.get_chan())
        me.party.leave(k)
        return True
    elif words[1] == "leader":
        if not k.nick:
            me.p("Nameless kobolds cannot lead parties.", True)
        else:
            me.party.owner = k
            game_print(k.display()+" has been made party leader.",
                       me.party.get_chan())
            return True
    return False


def cmd_study(words, k, target):
    r = find_research(words[1], lax=True)
    if not r:
        k.p("Research '"+words[1]+"' not found.")
        return False
    if k.familiar(r["name"]) >= 2:
        k.p("You have nothing more to learn about "+r["name"]+".")
        return False
    good = check_req(k.get_place(), [["research", r["name"]]], k)
    if good != "good":
        k.p("Can't study " +
            r["name"]+". The technology must be available to the tribe or another kobold must be very familiar with it.")
        return False
    prog = (k.smod("int")+k.skmod("research")+10)*2
    if k.tribe.has_building("Research Lab"):
        prog *= 2
    k.p("[n] studies "+r["name"]+" and makes " +
        str(prog)+" progress towards learning it.")
    k.gain_xp("research", prog/2)
    # int is already factored in
    k.get_familiar(r["name"], prog-(k.smod("int")*2))
    return True


def cmd_thesis(words, k, target):
    r = find_research(words[1], lax=True)
    if not r:
        k.p("Research '"+words[1]+"' not found.")
        return False
    if k.familiar(r["name"]) < 2:
        k.p("You aren't familiar enough with " +
            r["name"]+" to write a thesis about it.")
        return False
    if not k.has_item("Stone Tablet"):
        k.p("You need something to write your thesis on.")
        return False
    k.p("[n] writes a thesis on "+r["name"]+".")
    k.consume_item("Stone Tablet")
    th = spawn_item("Thesis", k)
    th.note = r["name"]
    return True


def cmd_domesticate(words, k, target):
    if target.farming["type"] == "None":
        k.p("That cannot be farmed.")
        return False
    place = k.get_place()
    if target.name in place.farmable:
        k.p("That is already domesticated.")
        return False
    prog = 10+(k.smod("int")+(k.skmod("farming")))
    prog = max(1, prog)
    if target.name not in place.dom_prog:
        place.dom_prog[target.name] = 0
    place.dom_prog[target.name] += prog
    if place.dom_prog[target.name] >= target.farming["diff"]:
        k.p("[n] has successfully domesticated "+target.name+"!")
        place.farmable.append(target.name)
        target.num -= 1
        if target.num <= 0:
            target.destroy("Domesticated")
        place.justbuilt = target.name
    else:
        k.p("[n] has made "+str(prog)+" progress towards domesticating "+target.name +
            ". ("+str(place.dom_prog[target.name])+"/"+str(target.farming["diff"])+")")
    k.gain_xp("farming", prog*2)
    k.get_familiar("Plant Domestication", prog*2)
    return True


def cmd_fish(words, k, target):
    k.equip_best("fishing")
    t = k.get_place()
    fish = False
    for l in t.special:
        if l in landmark_data and landmark_data[l].get("fish", False):
            fish = True
    if not fish:
        k.p("There's nothing to catch here.")
        return False
    ch = 10+((k.smod("str")+k.smod("dex")+k.skmod("fishing"))*3)
    ch += int(k.equip_bonus("fishing"))*3
    if chance(ch):
        s = min(5, math.floor(random.randint(1, ch)/25))
        exp = (s*10)+20
        i = spawn_item("Fish", k)
        specs = ["Crayfish", "Loach", "Catfish", "Trout", "Salmon", "Kingfish"]
        i.owner = specs[min(max(0, s), 5)]
        k.p("[n] goes fishing, and catches a lively "+i.owner+"!")
        i.size = s+1
        i.gain = [["Raw Fish", s+1]]
        bones = s*3
        if bones > 0:
            i.gain.append(["Bones", bones])
    else:
        k.p("[n] goes fishing, but fails to catch anything.")
        exp = 10
    k.gain_xp("fishing", exp)
    return True


def cmd_farm(words, k, target):
    k.equip_best("farming")
    if len(words) < 2:
        words.append("Raw Mushroom")
    f = None
    types = {}
    for i in item_data:
        if i.get("farming", None):
            if words[1].lower() in i["name"].lower() and not f:
                f = i
            if i["farming"]["type"] not in types:
                types[i["farming"]["type"]] = []
            types[i["farming"]["type"]].append(i)
    if f is None:
        k.p("That isn't a farmable item ("+words[1]+").")
        return False
    t = k.get_place()
    if isinstance(t, Tribe):
        t = k.world.get_tile(k.x, k.y, k.z)
    if k.party and k in k.party.owner.tribe.prison:
        tribe = k.party.owner.tribe
    else:
        tribe = k.tribe
    if not tribe:
        k.p("You are not in a tribe, so you don't have access to a seed cache.")
        return False
    elif f["name"] not in tribe.farmable:
        k.p("You haven't domesticated "+f["name"]+" yet.")
        return False
    for l in t.special:
        if "Farm" in l:
            ft = l.replace(" Farm", "")
            if ft in types and f not in types[ft]:
                k.p("You can't grow "+f["name"]+" in a "+ft+" Farm.")
                return False
    maxprog = t.farm_cap
    for x in types[f["farming"]["type"]]:
        if x["name"] in t.farming_prog and x != f:
            maxprog -= math.floor(t.farming_prog[x["name"]] /
                                  x["farming"]["prog"])*x["farming"]["prog"]
    if f["name"] not in t.farming_prog:
        t.farming_prog[f["name"]] = 0
    if t.farming_prog[f["name"]] >= maxprog:
        k.p("The "+f["farming"]["type"]+" Farm is already at capacity.")
        return False
    prog = 10+(k.smod("con")+(k.skmod("farming")*3))
    prog += int(k.equip_bonus("farming")/2)
    prog = max(1, prog)
    t.farming_prog[f["name"]] += prog
    if t.farming_prog[f["name"]] >= maxprog:
        t.farming_prog[f["name"]] = maxprog
        k.p("All possible farm work for this type of plant has been completed.")
        if isinstance(t, Tribe):
            t.justbuilt = f["name"]
    k.p("[n] has put "+str(prog)+" progress into farming "+f["name"] +
        ". ("+str(t.farming_prog[f["name"]])+"/"+str(maxprog)+")")
    k.gain_xp("farming", prog/2)
    k.get_familiar("Agriculture", prog)
    if k.accident(10-k.smod("con")):
        k.p("[n] threw their back out! This is some hard work!")
    return True


def cmd_mine(words, k, target):
    if k.z == 0 or k.dungeon:
        k.p("There's nothing to mine here.")
        return False
    k.equip_best("mining")
    if len(words) > 1:
        words[1] = words[1].lower()
    prog = ((k.smod("str")+k.skmod("mining"))*3)+10
    prog += k.equip_bonus("mining")
    prog = max(1, prog)
    t = k.world.get_tile(k.x, k.y, k.z)
    d = None
    if len(words) > 1 and words[1][0] in DIR_FULL:
        d = words[1][0]
    else:
        x = max(list(t.mineprog.values()))
        for p in t.mineprog:
            if p not in ['u', 'd'] and t.mineprog[p] == x:
                d = p  # dumber
    if not d:
        d = choice(list(DIR_FULL.keys()))
    t.mineprog[d] += prog
    tribe = t.get_tribe()
    y = []
    sp = math.floor(t.mineprog[d]/100)
    k.p("[n] has made "+str(prog)+" progress mining to the " +
        DIR_FULL[d]+". ("+str(t.mineprog[d])+"/100)")
    if k.has_trait("gemsight"):
        gemch = 20
    else:
        gemch = 5
    geo = None
    best = -10
    if tribe:
        search = tribe.kobolds
    elif k.party:
        search = k.party.k_members
    else:
        search = [k]
    for l in search:
        if l.skmod("geology")+l.smod("int") > best:
            geo = l
            best = l.skmod("geology")+l.smod("int")
    gemch += best
    res = "Stone Chunk"
    if chance(gemch):
        y.append(choice(["Topaz", "Ruby", "Onyx", "Quartz",
                 "Emerald", "Sapphire", "Opal", "Amethyst"]))
        if geo:
            geo.gain_xp("geology", 25)
    if chance(100-t.stability-(k.skmod("mining")*5)):
        k.p("The cavern rumbles ominously...")
    while t.mineprog[d] >= 100:
        t.mineprog[d] -= 100
        if tribe:
            tribe.space += 1
        if t.blocked[d]:
            t.blocked[d] = False
            t.get_border(d).blocked[OPP_DIR[d]] = False
            k.p("[n] has dug a tunnel through to the next tile!")
        else:
            t.cave_in(k, d)
        if t.resources[d] and t.mined[d] >= 0:
            res = t.resources[d]
        else:
            res = "Stone Chunk"
            t.mined[d] += 1
        y.append(res)
        t.stability -= 5
    if len(y) > 0:
        k.p("[n] has found some materials: "+", ".join(y))
        minedplus = 0
        for i in y:
            n = 1
            for z in item_data:
                if z["name"] == i:
                    n = random.randint(1, z.get("stack", 1))
            if tribe:
                m = spawn_item(i, tribe, n)
            else:
                m = spawn_item(i, t, n)
            if i != "Stone Chunk":
                minedplus += m.veinsize
        if tribe and sp > 0:
            k.p("[n]'s efforts have cleared "+str(sp)+" space for the tribe.")
        if "Stone Chunk" in y and t.mined[d] >= 0 and t.resources[d]:
            k.p("[n] has revealed a node of "+t.resources[d]+"!")
        elif res != "Stone Chunk" and res in y and chance((t.mined[d]+minedplus)*5):
            k.p("The "+res+" vein is depleted.")
            t.resources[d] = None
        if res in y:
            t.mined[d] += minedplus
    exp = prog+(len(y)*5)+(sp*5)
    k.gain_xp("mining", exp)
    ch = 10-k.smod("dex")
    if tribe and tribe.has_building("Stone Pillars"):
        ch = math.floor(ch/2)
    if k.accident(ch):
        k.p("[n] caused some rocks to collapse!")
    return True


def cmd_chop(words, k, target):
    if k.z != 0 or k.dungeon:
        k.p("That can only be done on the surface.")
        return False
    t = k.world.get_tile(k.x, k.y, k.z)
    if t.stability <= 0:
        k.p("There are no trees here to chop.")
        return False
    k.equip_best("woodcutting")
    if not k.equip or k.equip.tool != "woodcutting":
        k.p("You need an axe to chop a tree. Claws won't cut it.")
        return False
    prog = ((k.smod("str")+k.skmod("woodcutting"))*3)+10
    prog += k.equip_bonus("woodcutting")
    prog = max(1, prog)
    t.mineprog["w"] += prog
    k.p("[n] has made "+str(prog) +
        " progress chopping a tree. ("+str(t.mineprog["w"])+"/100)")
    exp = prog
    while t.mineprog["w"] >= 100:
        t.mineprog["w"] -= 100
        logs = random.randint(1, 4)
        branches = random.randint(1, 10)
        k.p("The tree is felled and yields "+str(logs) +
            " logs and "+str(branches)+" sticks.")
        if k.tribe:
            ct = k.world.find_tile_feature(10, k, "Elven Sanctuary", "special")
            if ct:
                k.tribe.gain_heat(1, "Elf")
                k.p("The local tree-huggers surely won't be happy to see this.")
        spawn_item("Wooden Log", t, logs)
        spawn_item("Wooden Stick", t, branches)
        exp += (logs*5)+branches+5
        t.stability -= 1
        if chance(10+t.stability-k.skmod("woodcutting")):
            bolds = []
            for l in k.world.kobold_list:
                if l.get_place() == t:
                    bolds.append(l)
            target = choice(bolds)
            if target:  # there should be at least one, the lumberjack themselves, but you never know
                target.p("[n] was crushed by the falling tree!")
                target.hp_tax(random.randint(5, 15),
                              "Timber!", dmgtype="bludgeoning")
    k.gain_xp("woodcutting", exp)
    ch = 10-k.smod("dex")
    if k.accident(ch):
        k.p("[n] was hit by a broken branch!")
    return True


async def cmd_spells(words, user, chan, w):
    pages = {}
    maxlevel = 0
    if len(words) > 1:
        sch = words[1].lower()
    else:
        sch = None
    for s in spell_data:
        if sch and sch not in s["school"]:
            continue
        l = str(s["level"])
        if s["level"] > maxlevel:
            maxlevel = s["level"]
        if l not in pages:
            pages[l] = []
        pages[l].append(s["name"]+" - "+s["desc"])
    embeds = []
    for l in range(maxlevel+1):
        if str(l) in pages:
            e = discord.Embed(type="rich", title="Level "+str(l) +
                              " Spells", description="\n".join(pages[str(l)]))
            embeds.append(e)
            e.set_footer(text="Showing level "+str(l)+" of " +
                         str(maxlevel)+". React to scroll.")
    if len(embeds) == 0:
        await chan.send("No spells of school '"+sch+"' found.")
        return False
    await embed_group(chan, embeds)
    return True


async def cmd_info(words, user, chan, w):
    info = []
    words[1] = words[1].lower()
    if len(words[1]) < 3 and words[1] not in ["cp", "ce", "me", "sp"]:
        await chan.send("Search terms must be at least 3 characters in length.")
        return
    if words[1][0] == "*":
        cat = words[1].replace("*", "")
    else:
        cat = None
    for r in building_data:
        if words[1] in r["name"].lower():
            info.append([r, "Building"])
    for r in research_data:
        if words[1] in r["name"].lower():
            info.append([r, "Research"])
    for r in spell_data:
        if words[1] in r["name"].lower():
            info.append([r, "Spell"])
    for r in creature_data:
        if words[1] in r["name"].lower():
            info.append([r, "Creature"])
    for i in item_data:
        if words[1] in i["name"].lower():
            info.append([i, "Item"])
        if cat and cat in i.get("cat", []):
            info.append([i, "Item"])
    for i in item_cats:
        if words[1] in i.lower():
            info.append(
                [{"name": i, "items": ", ".join(item_cats[i])}, "Item Category"])
    for r in craft_data:
        if words[1] in r["result"].lower():
            info.append([r, "Craft"])
    for r in landmark_data:
        if words[1] in r.lower():
            info.append([landmark_data[r], "Landmark"])
    for r in liquid_data:
        if words[1] in r.lower():
            liquid_data[r]["name"] = r
            info.append([liquid_data[r], "Liquid"])
    for r in trait_data:
        if words[1] in r.lower():
            trait_data[r]["name"] = r
            info.append([trait_data[r], "Trait"])
    for r in cmd_data:
        if words[1] in r["cmd"].lower() or words[1] in r.get("synonyms", []):
            if not r.get("console", False):
                info.append([r, "Command"])
    for r in skill_data:
        if words[1] in r.lower():
            info.append([skill_data[r], "Skill"])
        elif words[1] == skill_data[r]["stat"].lower():
            info.append([skill_data[r], "Skill"])
    embeds = []
    for a in info:
        if a[0] is None:
            continue
        title = a[0].get("name", a[0].get(
            "result", a[0].get("cmd", "???")))+" ("+a[1]+")"
        msg = []
        for b in a[0]:
            if b == "dmg":
                if a[0][b][2] > 0:
                    dstr = "+"+str(a[0][b][2])
                elif a[0][b][2] < 0:
                    dstr = str(a[0][b][2])
                else:
                    dstr = ""
                if a[0][b][0] > 0:
                    dstr = str(a[0][b][0])+"d"+str(a[0][b][1])+dstr
                msg.append(b+": "+dstr)
            elif b != "name" and b != "result" and b != "cmd":
                m = b+": "+str(a[0][b])
                m = m.replace("*", "\*")
                m = m.replace(":", "\:")
                msg.append(m)
        embeds.append(discord.Embed(
            type="rich", title=title, description="\n".join(msg)))
        embeds[len(embeds)-1].set_footer(text="Result "+str(len(embeds)) +
                                         " of "+str(len(info))+". Use the reactions to navigate results.")
    if len(embeds) > 0:
        await embed_group(chan, embeds)
    else:
        await chan.send("Nothing found for '"+words[1]+"'.")
    return True


def cmd_quit(words, me, p, force=False):
    if me.party and me.party.owner == me and not force:
        me.p("You can only quit if you're not the party leader.")
        return False
    me.p("[n] suffers an identity crisis and reverts to their birth name ("+me.name+").")
    me.nick = None
    me.vote = -1
    if me.party:
        action_queue.append(["delmember", me.party.get_chan(), me.d_user_id])
        if me.party.owner == me:
            eligible = []
            for m in me.party.k_members:
                if m.nick:
                    eligible.append(m)
            me.party.owner = choice(eligible)
            if me.party.owner:
                game_print(me.party.owner.display() +
                           " has been made party leader.", me.party.chan)
            else:
                mem = list(me.party.members)
                for m in mem:
                    if m.party:
                        m.party.leave(m)
    if me.tribe and me in me.tribe.kobolds:
        action_queue.append(["delmember", me.tribe.get_chan(), me.d_user_id])
        action_queue.append(
            ["delmember", "tribe-"+str(me.tribe.id)+"-chat", me.d_user_id])
    action_queue.append(["delrole", ROLENAMES[me.color], me.d_user_id])
    action_queue.append(["addrole", "Lost Soul", me.d_user_id])
    return True


async def cmd_seltest(words, user, chan, w):
    k = get_newbold(user, chan, w, test=True)
    if k:
        await chan.send("selected "+k.name)
    else:
        await chan.send("none got")


def get_newbold(user, chan, w, test=False, nt=False):
    nameless = []
    inselection = []
    selbolds = []
    spe = get_pdata(user.id, "sp_earned", 0)
    exed = get_pdata(user.id, "exiled_from", [])
    sel = get_pdata(user.id, "selection", {})
    for p in playerdata:
        if p == str(user.id):
            continue
        if len(playerdata[p].get("selection", {})) > 0:
            for s in playerdata[p]["selection"]:
                inselection.append(s)
    for k in w.kobold_list:
        if not k.nick:
            if k.d_user_id and user.id == k.d_user_id:  # returning player who left/quit
                nameless = [k]
                break
            elif k.tribe and k.tribe.id not in exed and not k.d_user_id and k.age >= 6 and not nt and str(k.id) not in sel and not k.has_trait("locked"):
                if str(k.id) in inselection:
                    selbolds.append(k)
                else:
                    nameless.append(k)
        elif k.d_user_id == user.id and not test:
            return None
    if len(nameless) < 1:
        nameless = selbolds
    if len(nameless) < 1:
        if spe == 0:  # want to make a new tribe, but this is a new player
            k = Kobold(w.tribes[0])
            k.tribe = None
            k.random_stats()
            k.z = -1
            nameless = [k]
        else:
            console_print("No nameless kobolds exist. Creating a new tribe")
            newtribe = Tribe(w)
            w.tribes.append(newtribe)
            nameless = list(newtribe.kobolds)
    av = []
    for x in nameless:
        if x.tribe:
            av.append(x.name+"["+str(x.tribe.id)+"]")
        else:
            av.append(x.name+"[-]")
    console_print(str(len(av))+" available: "+", ".join(av))
    return choice(nameless)


async def cmd_refund(words, user, chan, w):
    m = discord.utils.get(guild.members, nick=words[1])
    if m:
        sp = get_pdata(m.id, "sp", 10)
        playerdata[str(m.id)]["sp"] += int(words[2])
        await chan.send(words[1]+" has been refunded "+words[2]+" SP.")
        return True
    await chan.send("User not found.")
    return False


async def cmd_sp(words, user, chan, w):
    sp = get_pdata(user.id, "sp", 10)
    spe = get_pdata(user.id, "sp_earned", 0)
    await chan.send("You currently have "+str(sp)+" Soul Points. You have earned "+str(spe)+" Soul Points to date.")
    return False


async def show_selection(udm, sel, first=None):
    embeds = []
    a = 0
    for s in sel:
        e = discord.Embed(type="rich", description=sel[s])
        a += 1
        e.set_footer(
            text="React to scroll through choices. (showing "+str(a)+" of "+str(len(sel))+")")
        if first == s:
            embeds.insert(0, e)
        else:
            embeds.append(e)
    await embed_group(udm, embeds)


async def cmd_reroll(words, user, chan, w):
    if not user.dm_channel:
        udm = await user.create_dm()
    else:
        udm = user.dm_channel
    sel = get_pdata(user.id, "selection", {})
    if len(sel) < 4:
        newbold = get_newbold(user, chan, w)
        if not newbold:
            await chan.send("You already have a kobold.")
            return False
        sel[str(newbold.id)] = newbold.char_info(newbold, pr=False)
    else:
        await chan.send("You have 4 kobolds in your selection already.")
        return False
    embeds = []
    await udm.send("Added "+newbold.display()+" to your selection.")
    await show_selection(udm, sel, first=str(newbold.id))
    return True


async def cmd_newtribe(words, user, chan, w):
    if not user.dm_channel:
        udm = await user.create_dm()
    else:
        udm = user.dm_channel
    sel = get_pdata(user.id, "selection", {})
    if len(sel) > 4:
        await chan.send("You've already founded a new tribe. If you need to see the list of available kobolds again, type `!join`.")
        return False
    test = get_newbold(user, chan, w, nt=True)
    if not test:
        await chan.send("You already have a kobold.")
        return False
    elif test.d_user_id == user.id:
        await chan.send("Your soul is still bound to a kobold in this world. Use `!join` to reclaim them.")
        return False
    playerdata[str(user.id)]["selection"] = {}
    for k in test.tribe.kobolds:
        playerdata[str(user.id)]["selection"][str(k.id)
                                              ] = k.char_info(k, pr=False)
    await udm.send("New tribe founded. The following are the kobolds within it. Name one with `!name <birth name> <new name>` to claim them!")
    await show_selection(udm, playerdata[str(user.id)]["selection"])
    return True


async def cmd_join(words, user, chan, w):
    if not user.dm_channel:
        udm = await user.create_dm()
    else:
        udm = user.dm_channel
    sel = get_pdata(user.id, "selection", {})
    if len(sel) == 0:
        newbold = get_newbold(user, chan, w)
        if not newbold:
            cmd = "!party "+" ".join(words)
            cmd = cmd.replace("!join", "join")
            # console_print(cmd)
            words = cmd.split()
            me = None
            for k in w.kobold_list:
                if k.d_user_id == user.id:
                    me = k
                    break
            if me:
                cmd_party(words, me, None)
                return False
            else:
                await chan.send("You already have a kobold.")
                return False
        sel[str(newbold.id)] = newbold.char_info(newbold, pr=False)
    await udm.send("The following are the kobolds you can choose from. The info shown was retrieved at the time it was added to your selection and may not reflect their current status. You can take control of one by assigning them a name.\nYou can type `!reroll` to spend 10 Soul Points to add another kobold to your selection. You can have up to 4 kobolds in your selection at a time.\nWhen you've made a decision, type `!name <birth name> <new name>` to join!")
    await show_selection(udm, sel)
    return True


async def cmd_name(words, user, chan, w, wand=None):
    name = words[2]
    if len(name) > 32:
        await chan.send("Your name cannot be longer than 32 characters.")
        return False
    for c in name:
        if ord(c) > 256 or c == "/":
            await chan.send("This name contains an illegal character ("+c+").")
            return False
    newbold = None
    chief = True
    if not wand:
        sel = get_pdata(user.id, "selection", {})
        for k in w.kobold_list:
            if k.has_trait("locked"):
                continue
            if str(k.id) in sel and words[1].lower() == k.name.lower():
                newbold = k
                break
        nid = None
        if not newbold:
            for s in sel:
                msg = sel[s].split("\n")
                for m in msg:
                    if "Birth" in m:
                        m = m.replace("Birth name: ", "")
                        if words[1].lower() == m.lower():
                            nid = s
                            break
        elif newbold.nick:
            nid = str(newbold.id)
        if nid is not None:
            if len(sel) > 1:
                get_pdata(user.id, "sp", 10)
                playerdata[str(user.id)]["sp"] += 10
                await chan.send("That kobold is no longer available. You have been refunded 10 Soul Points (current balance: "+str(playerdata[str(user.id)]["sp"])+")")
            else:
                await chan.send("That kobold is no longer available. You can type `!join` to get a new selection.")
            del sel[nid]
            return False
        elif not newbold:
            await chan.send("Kobold not found. Ensure that you have spelled their birth name correctly.")
            return False
    else:
        sp = get_pdata(user.id, "sp", 10)
        if sp < 100:
            await chan.send("Not enough Soul Points. (have "+str(sp)+", need 100)")
            return False
        playerdata[str(user.id)]["sp"] -= 100
        newbold = Kobold(choice(w.tribes))
        newbold.tribe = None
        if wand["sex"] == "male":
            newbold.male = True
        else:
            newbold.male = False
        newbold.name = wand["name"]
        for st in newbold.s:
            newbold.s[st] = wand[st]
        newbold.color = newbold.get_color_for_stats()
        newbold.random_genomes()
        newbold.hp = newbold.max_hp
    wanderer = False
    if not newbold.tribe:  # wanderer
        newbold.tribe = choice(w.tribes)
        (newbold.x, newbold.y, newbold.z) = (
            newbold.tribe.x, newbold.tribe.y, newbold.tribe.z)
        newbold.tribe.add_bold(newbold)
        wanderer = True
    newtribe = newbold.tribe
    for k in w.kobold_list:
        if k.tribe == newtribe and k.nick:
            chief = False
    newbold.nick = name
    if not newbold.d_user_id:
        newbold.ap_gain(4)
    newbold.d_user_id = user.id
    console_print(user.name+" has joined as "+newbold.name +
                  " (now named "+newbold.nick+")", hp=True)
    if not newbold.party and not isinstance(newbold.get_place(), Tribe):
        Party(newbold)
    if wanderer:
        newbold.p("A kobold named "+newbold.nick +
                  " has arrived from a distant land.")
    else:
        newbold.p(newbold.name+" has adopted a new tribal name: " +
                  newbold.nick+".")
    if chief:
        newtribe.chieftain = newbold
        newbold.p("The kobolds elect [n] as their first chieftain.")
        action_queue.append(["addrole", "Chieftain", user.id])
    newbold.cp = newbold.max_cp
    if w != sandbox:
        try:
            await user.edit(nick=name)
        except:
            pass
        for c in guild.channels:
            if "party" in c.name or "tribe" in c.name:
                action_queue.append(["delmember", c.name, user.id])
        action_queue.append(["addrole", ROLENAMES[newbold.color], user.id])
        action_queue.append(["delrole", "Lost Soul", user.id])
    if newbold.party:
        action_queue.append(["addmember", newbold.party.get_chan(), user.id])
        await chan.send("You have joined the game! Your current channel is #"+newbold.party.get_chan()+" on the server.")
    p = newbold.get_place()
    if isinstance(p, Tribe):
        action_queue.append(["addmember", p.get_chan(), user.id])
        action_queue.append(["addmember", "tribe-"+str(p.id)+"-chat", user.id])
        await chan.send("You have joined the game! Your current channel is #"+p.get_chan()+" on the server.")
    playerdata[str(user.id)]["selection"] = {}
    return True


async def log_exception(info=None):
    chan = discord.utils.get(guild.channels, name="exception-log")
    if chan:
        # if ship is not None: await chan.send("Exception caught on ship "+ship)
        if info:
            await chan.send(info)
        m = traceback.format_exc().split("\n")
        msg = ""
        first = False
        for q in m:
            if len(msg+"\n"+q) >= 2000:
                await chan.send(msg)
                msg = ""
                first = False
            if first:
                msg += "\n"+q
            else:
                first = True
                msg += q
        if len(msg) > 0:
            await chan.send(msg)


def console_print(m, hp=False, lp=False):
    global console_crosspost
    msg = "["+time.strftime("%H:%M:%S")+"] "
    if hp:
        msg += "[HIGH] "
    msg += str(m)
    print(msg)
    if (console_crosspost or hp) and not lp:
        console_queue.append(msg)


def game_print(msg, chan, pin=False):
    if not chan:
        return
    if chan not in post_queue:
        post_queue[chan] = []
    if pin:
        msg = "<<PINTHIS>>"+msg
    post_queue[chan].append(msg)


async def multi_select(chan, search, me, startininv=True, place="any", type=None, landmarks=False, ordering=False):
    target = None
    first = False
    if "-first" in search:
        first = True
        search = search.replace("-first", "")
    targets = find_item_multi(search.lower(), me, startininv, place, type)
    if landmarks:
        tile = me.world.get_tile(me.x, me.y, me.z)
        for l in tile.special:
            if search in l.lower():
                targets.append(l)
    if not chan:
        if len(targets) == 0:
            return None
        else:
            return targets[0]
    if len(targets) == 0:
        await chan.send("Item '"+search+"' not found.")
    elif first:
        target = targets[0]
    elif len(targets) > 1:
        await chan.send("Multiple matches found, please select the one you want.")
        embeds = []
        for t in targets:
            if isinstance(t, str):
                e = discord.Embed(type="rich", title=t,
                                  description=landmark_data[t]["desc"])
            else:
                e = t.examine(me, True)
            embeds.append(e)
            e.set_footer(text="Showing item "+str(len(embeds))+" of "+str(len(targets)) +
                         ". Use the reactions to scroll, and click the checkmark to confirm your choice.")
        if me.nick and not ordering:
            # HAH. I have hopefully defeated you :J
            user = discord.utils.get(guild.members, id=me.d_user_id)
        else:
            user = None
        tt = await embed_group(chan, embeds, user)
        if tt is not None:
            target = targets[tt]
        else:
            await chan.send("Timed out.")
    else:
        target = targets[0]
    return target


def find_item_multi(name, me, startininv=True, place="any", type=None, ignore_displays=False):
    #console_print("searching for "+name+" among items (multi)")
    targets = []
    displays = []
    t = me.get_place()
    if isinstance(t, Tribe) and me in t.tavern:
        t = me.world.get_tile(me.x, me.y, me.z)
    if place == "kennel":
        scope = list(me.tribe.kennel_items)
    elif startininv:
        if place != "ground":
            scope = list(me.items)+list(me.worns.values())
        if place != "inv":
            scope += list(t.items)
    else:
        if place != "inv":
            scope = list(t.items)
        if place != "ground":
            scope += list(me.items)+list(me.worns.values())
    for i in scope:
        if not i:
            continue
        if i.name.lower() == name and i.display() not in displays and (not type or i.type in type):
            targets.append(i)
            if not ignore_displays:
                displays.append(i.display())
    for i in scope:
        if not i:
            continue
        if name in i.display().lower() and i.display() not in displays and (not type or i.type in type):
            targets.append(i)
            if not ignore_displays:
                displays.append(i.display())
    return targets


def find_item(name, me, startininv=True, type=None, hasliquid=False):
    #console_print("searching for "+name+" among items")
    t = me.get_place()
    if isinstance(t, Tribe) and me in t.tavern:
        t = me.world.get_tile(me.x, me.y, me.z)
    if startininv:
        scope = list(me.items)+list(t.items)
    else:
        scope = list(t.items)+list(me.items)
    for i in scope:
        if i.name.lower() == name and (not type or i.type == type) and (not hasliquid or i.liquid_units > 0):
            return i
    for i in scope:
        if name in i.display().lower() and (not type or i.type == type) and (not hasliquid or i.liquid_units > 0):
            return i
    return None


def find_creature_i(name, me):
    crs = []
    if me.party:
        crs.extend(me.party.c_members)
    p = me.get_place()
    if isinstance(p, Tribe):
        crs.extend(p.kennel)
    else:
        crs.extend(p.pasture)
    for e in me.world.encounters:
        if e.place == p:
            crs.extend(e.creatures)
    for c in crs:
        if name.lower() in c.name.lower():
            return c


def find_kobold(name, area=None, w=None):
    if not w:
        w = world
    #console_print("looking for "+name)
    for k in w.kobold_list:
        if area and k.get_place() != area:
            continue
        if k.name.lower() == name.lower() or (k.nick and k.nick.lower() == name.lower()):
            return k
    for k in w.kobold_list:
        if area and k.get_place() != area:
            continue
        if name.lower() in k.get_name().lower():
            return k
    return None


def find_spell(name, lax=True):
    for s in spell_data:
        if s["name"] == name:
            return s
        elif lax and name.lower() in s["name"].lower():
            return s
    return None


def find_craft(name, lax=True):
    for c in craft_data:
        if c["result"].lower() == name.lower():
            return c
        elif lax:
            wrs = c["result"].lower().split()
            for w in wrs:
                if " "+name.lower() in " "+w.lower():
                    return c
                if " "+name.lower() in " "+c["result"].lower():
                    return c
    return None


def find_creature(name, lax=True):
    for c in creature_data:
        if c["name"] == name:
            return c
        elif lax and name.lower() in c["name"].lower():
            return c
    return None


def find_research(name, lax=True):
    for r in research_data:
        if r["name"] == name:
            return r
        elif lax and name.lower() in r["name"].lower():
            return r
    return None


def find_building(name, lax=True):
    for r in building_data:
        if r["name"] == name:
            return r
        elif lax and name.lower() in r["name"].lower():
            return r
    return None


async def cmd_spawn(words, user, chan, w):
    try:
        k = find_kobold(words[1], w=w)
    except:
        k = None
    if k:
        i = spawn_item(words[2], k)
        i.num = i.stack
        k.p("[n] discovers a "+i.display()+" in their pockets.")
    else:
        await chan.send("Kobold "+words[1]+" not found")


async def cmd_unlockall(words, user, chan, w):
    for t in w.tribes:
        for r in research_data:
            if r['name'] not in t.research:
                t.research.append(r['name'])
        for b in building_data:
            if b['name'] not in t.buildings and not b.get("landmark", False):
                t.buildings.append(b['name'])
    await chan.send("Research and buildings unlocked")


async def cmd_spencounter(words, user, chan, w):
    try:
        k = find_kobold(words[1], w=w)
    except:
        k = None
    if k:
        try:
            n = int(words[2])
        except:
            n = 1
        Encounter(w, k.get_place(), n, k.z, words[3])
    else:
        await chan.send("Kobold "+words[1]+" not found")


async def cmd_tribefix(words, user, chan, w):
    try:
        k = find_kobold(words[1], w=w)
    except:
        k = None
    if k:
        tribe = None
        tribeid = int(words[2])
        for t in w.tribes:
            if t.id == tribeid:
                tribe = t
        if not tribe:
            await chan.send("Tribe "+str(tribeid)+" not found.")
            return False
        cmd_leave([], k, None)
        k.tribe = tribe
        (k.x, k.y, k.z) = (tribe.x, tribe.y, tribe.z)
        await chan.send("Kobold tribe reassigned and moved.")
    else:
        await chan.send("Kobold "+words[1]+" not found")


async def cmd_partyfix(words, user, chan, w):
    for k in w.kobold_list:
        if k.nick and not k.party and not isinstance(k.get_place(), Tribe):
            Party(k)
            console_print("Fixed "+k.nick)


async def cmd_givespell(words, user, chan, w):
    try:
        k = find_kobold(words[1], w=w)
    except:
        k = None
    if k:
        if words[2] in k.spells:
            k.spells.remove(words[2])
            await chan.send("Removed "+words[2]+" spell from kobold "+k.get_name())
        else:
            k.spells.append(words[2])
            await chan.send("Gave "+words[2]+" spell to kobold "+k.get_name())
    else:
        await chan.send("Kobold "+words[1]+" not found")


async def cmd_familiarize(words, user, chan, w):
    try:
        k = find_kobold(words[1], w=w)
    except:
        k = None
    if k:
        for r in research_data:
            k.familiarity[r["name"]] = r["diff"]*2
        await chan.send("Set all familiarities of kobold "+k.get_name())
    else:
        await chan.send("Kobold "+words[1]+" not found")


async def cmd_kvar(words, user, chan, w):
    try:
        k = find_kobold(words[1], w=w)
    except:
        k = None
    if k:
        try:
            v = int(words[3])
        except:
            if words[3][0] == "t":
                v = True
            elif words[3][0] == "f":
                v = False
            elif words[3][0] == "n":
                v = None
            elif words[3] == "[]":
                v = []
            else:
                v = words[3]
        if words[2] in k.s:
            k.s[words[2]] = v
        else:
            setattr(k, words[2], v)
        await chan.send("Set attribute "+words[2]+" of kobold "+k.get_name()+" to "+str(v)+" (type "+str(type(v))+")")
    else:
        await chan.send("Kobold "+words[1]+" not found")


async def cmd_setheat(words, user, chan, w):
    tribe = None
    for t in w.tribes:
        if t.id == int(words[1]):
            tribe = t
    if tribe:
        try:
            v = int(words[2])
        except:
            await chan.send("Invalid heat amount")
            return False
        tribe.heat_faction[words[3]] = v
        await chan.send("Set "+words[3]+" heat of tribe "+tribe.name+" ("+str(tribe.id)+") to "+str(v))
    else:
        await chan.send("Tribe "+words[1]+" not found")


async def cmd_clone(words, user, chan, w):
    global sandbox
    file = shelve.open("klsave", 'r')
    sandbox = file['world']
    file.close()
    for k in sandbox.kobold_list:
        if k.d_user_id != user.id:
            k.d_user_id = 0
            k.nick = None
        if k.party and k.party.id < 8989:
            k.party.id += 8989
    for t in sandbox.tribes:
        t.id += 89
    await chan.send("Main world cloned to sandbox.")


async def cmd_tvar(words, user, chan, w):
    tribe = None
    for t in w.tribes:
        if t.id == int(words[1]):
            tribe = t
    if tribe:
        try:
            v = int(words[3])
        except:
            if words[3][0] == "t":
                v = True
            elif words[3][0] == "f":
                v = False
            else:
                v = words[3]
        setattr(tribe, words[2], v)
        await chan.send("Set attribute "+words[2]+" of tribe "+tribe.name+" ("+str(tribe.id)+") to "+str(v)+" (type "+str(type(v))+")")
    else:
        await chan.send("Tribe "+words[1]+" not found")


async def cmd_trait(words, user, chan, w):
    try:
        k = find_kobold(words[1], w=w)
    except:
        k = None
    if k:
        if k.has_trait(words[2]):
            k.del_trait(words[2])
            await chan.send(words[2]+" trait removed from "+k.get_name())
        else:
            k.add_trait(words[2])
            await chan.send(words[2]+" trait added to "+k.get_name())
    else:
        await chan.send("Kobold "+words[1]+" not found")


async def cmd_reboot(words, user, chan, w):
    try:
        save_game()
        await chan.send("Game saved. Logging out.")
        await clive.logout()
    except Exception as e:
        await chan.send("Couldn't save game. Will not reboot.")
        await chan.send(e)
        await log_exception()


async def cmd_repopulate(words, user, chan, w):
    nests = 0
    for m in w.map:
        if len(w.map[m].special) == 0 and chance(5):
            w.map[m].landmarks()
        if "Ant Nest" in w.map[m].special:
            nests += 1
    await chan.send("Repopulated. btw, there are "+str(nests)+" ant nests in generated tiles")


async def cmd_landmark(words, user, chan, w):
    if words[1] == "anywhere":
        ants = choice(list(w.map.keys()))
        w.map[ants].special.append(words[2])
        await chan.send("Made a "+words[2]+" landmark at "+str((w.map[ants].x, w.map[ants].y, w.map[ants].z)))
    else:
        try:
            k = find_kobold(words[1], w=w)
        except:
            k = None
        if k:
            t = k.get_place()
            if isinstance(t, Tile):
                if words[2] in t.special:
                    t.special.remove(words[2])
                    await chan.send("Removed a "+words[2]+" landmark at "+words[1])
                else:
                    t.special.append(words[2])
                    await chan.send("Made a "+words[2]+" landmark at "+words[1])
            else:
                await chan.send("Kobold must be in overworld")
        else:
            await chan.send("Kobold "+words[1]+" not found")


async def cmd_findbold(words, user, chan, w):
    try:
        k = find_kobold(words[1], w=w)
    except:
        k = None
    if k:
        await chan.send("Found "+k.get_name()+" at "+",".join([k.x, k.y, k.z]))
    else:
        await chan.send("Kobold "+words[1]+" not found")


async def cmd_spawne(words, user, chan, w):
    try:
        k = find_kobold(words[1], w=w)
    except:
        k = None
    if k:
        t = k.get_place()
        t.spawn_encounter(words[2])
        await chan.send("Spawned an encounter.")
    else:
        await chan.send("Kobold "+words[1]+" not found")


async def cmd_makechief(words, user, chan, w):
    try:
        k = find_kobold(words[1], w=w)
    except:
        k = None
    if k and k.tribe:
        k.tribe.chieftain = k
        await chan.send(k.get_name()+" made chieftain of their tribe")
    else:
        await chan.send("Kobold not found")


async def cmd_ageup(words, user, chan, w):
    try:
        k = find_kobold(words[1], w=w)
    except:
        k = None
    if k:
        while k.age < 6:
            k.age_up()
            k.age += 1
        await chan.send(k.get_name()+" aged to adult")
    else:
        await chan.send("Kobold not found")


async def cmd_forcetunnel(words, user, chan, w):
    try:
        k = find_kobold(words[1], w=w)
    except:
        k = None
    if k:
        p = w.get_tile(k.x, k.y, k.z)
        d = choice(list(OPP_DIR.keys()))
        p.blocked[d] = False
        await chan.send(k.get_name()+" tunnel dug to the "+DIR_FULL[d])
    else:
        await chan.send("Kobold not found")


async def cmd_forcehatch(words, user, chan, w):
    for k in w.kobold_list:
        for i in k.items:
            if i.type == "egg":
                i.hatch()
    for m in w.map:
        for i in w.map[m].items:
            if i.type == "egg":
                i.hatch()
    for t in w.tribes:
        for i in t.items:
            if i.type == "egg":
                i.hatch()


async def cmd_forceegg(words, user, chan, w):
    try:
        k = find_kobold(words[1], w=w)
    except:
        k = None
    if k:
        try:
            l = find_kobold(words[2], w=w)
        except:
            l = None
        if l:
            egg = spawn_item("Kobold Egg", l)
            egg.kobold = make_baby(k, l)
            l.p("[n] has discovered an egg.")
            return True
    await chan.send("One or both kobolds not found")


async def cmd_forcebreed(words, user, chan, w):
    try:
        k = find_kobold(words[1], w=w)
    except:
        k = None
    if k:
        try:
            l = find_kobold(words[2], w=w)
        except:
            l = None
        if l:
            k.breed(l, force=True)
            return True
    await chan.send("One or both kobolds not found")


async def cmd_backup(words, user, chan, w):
    save_game("backup/klsave")
    await chan.send("Backup saved.")
    return True


async def cmd_loadbackup(words, user, chan, w):
    load_game("backup/klsave")
    await chan.send("Backup loaded.")
    return True


async def cmd_pdbackup(words, user, chan, w):
    global playerdata
    file = shelve.open("backup/klsave", 'r')
    if 'playerdata' in file:
        playerdata = file['playerdata']
    await chan.send("Backup player data loaded.")
    return True


async def cmd_mc(words, user, chan, w):
    await handle_final_orders(w)
    w.month_change()
    await chan.send("Month changed.")


async def cmd_refresh(words, user, chan, w):
    refresh_data()
    await chan.send("Data refreshed.")


async def cmd_reset(words, user, chan, w):
    global world, sandbox, guild
    if w == sandbox:
        sandbox = World()
        sandbox.tid = 89
    else:
        bolds = list(w.kobold_list)
        for k in bolds:
            if k.d_user_id and k.nick:
                try:
                    k.die("Big Crunch")
                except:
                    console_print("Couldn't kill "+k.get_name())
                    await log_exception()
        for p in playerdata:
            playerdata[p]["selection"] = {}
        for c in guild.channels:
            if "tribe" in c.name or "party" in c.name:
                await c.delete()
        world = World()
    await chan.send("World reset.")


async def do_msg_queue():
    global console_queue, guild
    if not guild:
        return
    chan = discord.utils.get(guild.channels, name="console")
    if chan:
        msg = ""
        msgsent = []
        first = False
        for q in console_queue:
            msgsent.append(q)
            if len(msg+"\n"+q) >= 2000:
                if len(msg) > 0 and len(msg) < 2000:
                    await chan.send(msg)
                msg = ""
                first = False
            if first:
                msg += "\n"+q
            else:
                first = True
                msg += q
        if len(msg) > 0 and len(msg) < 2000:
            await chan.send(msg)
        for m in msgsent:
            if m in console_queue:
                console_queue.remove(m)


async def do_post_queue():
    global post_queue, guild
    if not guild:
        return
    keys = list(post_queue.keys())
    for p in keys:
        channel = discord.utils.get(guild.channels, name=p)
        msg = []
        for m in post_queue[p]:
            msg.append(m)
        if channel:
            s = ""
            for m in msg:
                pin = False
                if len(s+"\n"+m) > 2000:
                    if "📌" in s:
                        s = s.replace("📌", "")
                        pin = True
                    if len(s) < 2000:
                        post = await channel.send(s)
                    if pin:
                        await post.pin()
                    s = ""
                s += "\n"+m
            if len(s) > 0:
                if "📌" in s:
                    s = s.replace("📌", "")
                    pin = True
                post = await channel.send(s)
                if pin:
                    await post.pin()
        for m in msg:
            post_queue[p].remove(m)


async def confirm_prompt(chan, msg, confirm=None):
    e = discord.Embed(type="rich", title="Confirmation", description=msg)
    e.set_footer(text="React with 👍 to continue, or 👎 to abort.")
    message = await chan.send(None, embed=e)
    await message.add_reaction('👍')
    await message.add_reaction('👎')
    conf = False
    emoji = ''
    while True:
        if emoji == '👍':
            conf = True
            break
        elif emoji == '👎':
            break

        def check(m, shrug):
            return m.message == message
        to = 30.0
        if isinstance(chan, discord.DMChannel):
            to = 180.0
        try:
            res = await clive.wait_for("reaction_add", timeout=to, check=check)
        except:
            res = None
        if res == None:
            break
        # Example: 'MyBot#1111'
        if str(res[1]) != BOT_NAME and (not confirm or res[1] == confirm):
            emoji = str(res[0].emoji)
            if not isinstance(chan, discord.DMChannel):
                await message.remove_reaction(res[0].emoji, res[1])
    try:
        await message.delete()
    except:
        pass
    return conf


async def embed_group(chan, embeds, confirm=None):
    message = await chan.send(None, embed=embeds[0])
    await message.add_reaction('⏮')
    await message.add_reaction('◀')
    await message.add_reaction('▶')
    await message.add_reaction('⏭')
    await message.add_reaction('❌')
    await message.add_reaction('✅')
    i = 0
    emoji = ''
    while True:
        if emoji == '⏮':
            i = 0
            await message.edit(embed=embeds[i])
        elif emoji == '◀':
            i -= 1
            if i < 0:
                i = len(embeds)-1
            await message.edit(embed=embeds[i])
        elif emoji == '▶':
            i += 1
            if i > len(embeds)-1:
                i = 0
            await message.edit(embed=embeds[i])
        elif emoji == '⏭':
            i = len(embeds)-1
            await message.edit(embed=embeds[i])
        elif emoji == '✅':
            await message.delete()
            return i
        elif emoji == '❌':
            await message.delete()
            return None

        def check(m, shrug):
            return m.message == message
        to = 30.0
        if isinstance(chan, discord.DMChannel):
            to = 180.0
        try:
            res = await clive.wait_for("reaction_add", timeout=to, check=check)
        except:
            res = None
        if res == None:
            break
        # Example: 'MyBot#1111'
        if str(res[1]) != BOT_NAME and (not confirm or res[1] == confirm):
            emoji = str(res[0].emoji)
            if not isinstance(chan, discord.DMChannel):
                await message.remove_reaction(res[0].emoji, res[1])
    try:
        if not isinstance(chan, discord.DMChannel):
            await message.clear_reactions()
        if confirm:
            await message.delete()
        else:
            embeds[i].set_footer(text="")
            await message.edit(embed=embeds[i])
    except:
        pass
    return None


async def edit_wanderer(chan, user=None):
    pid = str(user.id)
    k = get_pdata(pid, "editing", None)
    if not k:
        rs = random.randint(0, 1)
        if rs == 1:
            sex = "male"
        else:
            sex = "female"
        playerdata[pid]["editing"] = {"name": kobold_name(
        ), "nick": "???", "sex": sex, "str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10, "color": "brown"}
    ed = playerdata[pid]["editing"]
    e = discord.Embed(type="rich", title="Editing wanderer",
                      description="Setting up, please wait")
    message = await chan.send(None, embed=e)
    await message.add_reaction('⬆️')
    await message.add_reaction('⬇️')
    await message.add_reaction('◀')
    await message.add_reaction('▶')
    await message.add_reaction('🎲')
    await message.add_reaction('📛')
    await message.add_reaction('⚧')
    await message.add_reaction('❌')
    i = 0
    emoji = ''
    stat_sort = {}
    sel = 0
    while True:
        if emoji == '⬆️':
            sel -= 1
            if sel < 0:
                sel = 5
        elif emoji == '⬇️':
            sel += 1
            if sel > 5:
                sel = 0
        elif emoji == '◀':
            if ed[STATS[sel]] > 6:
                ed[STATS[sel]] -= 1
        elif emoji == '▶':
            if ed[STATS[sel]] < 14 and stotal < 60:
                ed[STATS[sel]] += 1
        elif emoji == '🎲':
            points = 24
            for st in STATS:
                ed[st] = 6
            while points > 0:
                st = choice(STATS)
                if ed[st] < 14:
                    ed[st] += 1
                    points -= 1
        elif emoji == '📛':
            ed["name"] = kobold_name()
        elif emoji == '⚧':
            if ed["sex"] == "male":
                ed["sex"] = "female"
            else:
                ed["sex"] = "male"
        elif emoji == '❌':
            break
        msg = "Birth name: "+ed["name"]+"\nTribal name: " + \
            ed["nick"]+"\nSex: "+ed["sex"]+"\n\nBase stats:\n"
        stotal = 0
        for s in range(6):
            if sel == s:
                msg += ":arrow_forward:"
            else:
                msg += ":blue_square:"
            msg += STATS[s]+": "+str(ed[STATS[s]])+"\n"
            stotal += ed[STATS[s]]
            stat_sort[STATS[s]] = ed[STATS[s]]
        msg += "Unallocated stat points: "+str(60-stotal)+"\n"
        m = sorted(stat_sort.items(), key=lambda kv: kv[1])
        if m[4][1] == m[5][1]:
            color = "brown"
        else:
            color = STAT_COLOR[m[5][0]]
        ed["color"] = color
        msg += "Color: "+color+"\n\n"
        msg += "Info: Click :arrow_up:/:arrow_down: to select a stat, and :arrow_backward:/:arrow_forward: to decrease or increase that stat. Color is determined based on the highest stat, or brown if there's a tie. Stats must be in the range of 6-14 inclusive.\n:game_die: - Randomize stats\n:name_badge: - Randomize birth name\n:transgender_symbol: - Switch sex\n:x: - Close this screen (edits will remain intact but not be saved)\nTo finalize and give your wanderer a tribal name, use `!wanderer save <name>`. If this times out, use `!wanderer edit` to bring this screen back up (current edits will remain intact)."
        e = discord.Embed(
            type="rich", title="Editing wanderer", description=msg)
        e.set_footer(text="React to make changes.")
        await message.edit(embed=e)

        def check(m, shrug):
            return m.message == message
        try:
            res = await clive.wait_for("reaction_add", timeout=180.0, check=check)
        except:
            res = None
        if res == None:
            break
        if str(res[1]) != BOT_NAME and (not user or res[1] == user):  # Example: 'MyBot#1111'
            emoji = str(res[0].emoji)
            if not isinstance(chan, discord.DMChannel):
                await message.remove_reaction(res[0].emoji, res[1])
    if not isinstance(chan, discord.DMChannel):
        await message.clear_reactions()
    e.set_footer(text="")
    await message.edit(embed=e)
    return None


async def print_routine(r, chan):
    rl = []
    rcount = 0
    for a in r:
        rl.append(str(rcount)+". "+a)
        rcount += 1
    e = discord.Embed(type="rich", title="Editing routine",
                      description="\n".join(rl))
    await chan.send(None, embed=e)


async def print_tasks(tribe, chan):
    rl = []
    rcount = 0
    for a in tribe.tasks:
        m = str(rcount)+". "
        m += a[0]+" - "
        if not a[1]:
            m += "Repeat as much as possible"
        elif a[1] == "times":
            m += "Repeat "+a[2]+" times"
        elif a[1] == "space":
            m += "Repeat until the den has "+a[2]+" space"
        elif a[1] == "farm_prog":
            m += "Repeat until "+a[3]+" crop progress is at "+a[2]
        elif a[1] == "farm_cap":
            m += "Repeat until farm capacity is at "+a[2]
        elif a[1] == "items":
            m += "Repeat until "+a[2]+" "+a[3]+" in storage"
        else:
            m += "Unknown break (this is probably a bug)"
        if not a[4]:
            m += " (Do not use tools)"
        else:
            m += " (Use tools)"
        rl.append(m)
        rcount += 1
    e = discord.Embed(type="rich", title="Tribe tasks",
                      description="\n".join(rl))
    await chan.send(None, embed=e)


async def cmd_task(words, me, chan):
    if len(words) > 1:
        if me.tribe:
            incharge = me.tribe.overseer
            if not incharge:
                incharge = me.tribe.chieftain
        if not me.tribe or me != incharge:
            me.p("Only the overseer can modify the task list. (Anyone can view the list by just typing `!tasks`)")
        elif words[1] == "add":
            if len(words) < 3:
                await chan.send("Please specify a command to add.")
                return False
            cmd = words[2].replace("!", "").lower()
            words = " ".join(words).split(" ", 2)
            if words[2][0] == "-":
                words[2] = words[2].replace("-", "")
            if words[2][0] != "!":
                words[2] = "!"+words[2]
            a = None
            for c in cmd_data:
                if c["cmd"] == cmd or cmd in c.get("synonyms", []):
                    a = c
                    break
            if a:
                if not a.get("task", False):
                    await chan.send("Can't add that command to a task.")
                    return
                me.tribe.tasks.append([words[2], None, None, None, True])
                await chan.send("Added "+words[2]+" to task list.")
            else:
                await chan.send("Command not found.")
        elif words[1] in ["until", "condition", "conditional", "stop", "break"]:
            words = " ".join(words).split(" ", 5)
            for x in range(5):
                words.append(None)
            s = None
            try:
                s = int(words[2])
            except:
                for a in me.tribe.tasks:
                    if words[2] in a[0]:
                        s = me.tribe.tasks.index(a)
            if s is not None:
                breaks = ["items", "farm_prog", "farm_cap", "space", "times"]
                if not words[3]:
                    me.tribe.tasks[s][1] = None
                    me.tribe.tasks[s][2] = None
                    me.tribe.tasks[s][3] = None
                    await chan.send("Removed break from task "+me.tribe.tasks[s][0])
                    return True
                if words[3] not in breaks:
                    await chan.send("Invalid type '"+str(words[3])+"'. Must be one of the following: "+", ".join(breaks))
                    return False
                if words[3] == "farm_prog":
                    found = None
                    for i in item_data:
                        if str(words[5]).lower() in i["name"].lower():
                            found = i
                            words[5] = i["name"]
                    if not found or not found.get("farming", None):
                        await chan.send("'"+str(words[5])+"' (argument2) is not a valid crop.")
                        return False
                if words[3] == "items":
                    found = None
                    for i in item_data:
                        if str(words[5]).lower() in i["name"].lower():
                            found = i
                            words[5] = i["name"]
                    if not found:
                        await chan.send("'"+str(words[5])+"' (argument2) is not a valid item.")
                        return False
                try:
                    am = int(words[4])
                except:
                    await chan.send("'"+str(words[4])+"' (argument1) is not a valid number.")
                    return False
                if len(words) >= 4:
                    me.tribe.tasks[s][1] = words[3]
                if len(words) >= 5:
                    me.tribe.tasks[s][2] = words[4]
                if len(words) >= 6:
                    me.tribe.tasks[s][3] = words[5]
                await chan.send("Added break to task "+str(s)+": "+str(me.tribe.tasks[s]))
            else:
                await chan.send("Task not found.")
        elif "tool" in words[1]:
            s = None
            try:
                s = int(words[2])
            except:
                for a in me.tribe.tasks:
                    if words[2] in a[0]:
                        s = me.tribe.tasks.index(a)
            if s is not None:
                if len(words) < 4:
                    if me.tribe.tasks[s][4]:
                        words.append("false")
                    else:
                        words.append("true")
                if words[3][0].lower() == "t":
                    me.tribe.tasks[s][4] = True
                    await chan.send("Kobolds performing this task will use tools")
                elif words[3][0].lower() == "f":
                    me.tribe.tasks[s][4] = False
                    await chan.send("Kobolds performing this task will NOT use tools")
                else:
                    await chan.send("True or false, please.")
                    return False
            else:
                await chan.send("Task not found.")
        elif words[1] in ["remove", "delete"]:
            s = None
            try:
                s = int(words[2])
            except:
                for a in me.tribe.tasks:
                    if words[2] in a[0]:
                        s = me.tribe.tasks.index(a)
            if s is not None and len(me.tribe.tasks) > s:
                rem = me.tribe.tasks.pop(s)
                await chan.send("Task "+str(s)+" (`"+str(rem)+"`) removed from task list.")
            else:
                await chan.send("Task not found.")
        elif words[1] == "move":
            try:
                s = int(words[2])
            except:
                s = None
            try:
                t = int(words[3])
            except:
                t = None
            if s is not None and t is not None:
                (me.tribe.tasks[s], me.tribe.tasks[t]) = (
                    me.tribe.tasks[t], me.tribe.tasks[s])
                await chan.send("Actions "+str(s)+" and "+str(t)+" swapped places.")
            else:
                await chan.send("One or both actions not found.")
    await print_tasks(me.tribe, chan)


async def cmd_routine(words, user, chan, w):
    pid = str(user.id)
    if words[1] == "new":
        playerdata[pid]["rediting"] = []
        await chan.send("Creating new routine for editing.")
        await print_routine(playerdata[pid]["rediting"], chan)
    elif words[1] == "edit":
        if len(words) < 3:
            await chan.send("Please specify a routine to edit.")
            return False
        if words[2] in get_pdata(pid, "routines", {}):
            playerdata[pid]["rediting"] = list(
                playerdata[pid]["routines"][words[2]])
            await chan.send("Opened routine '"+words[2]+"' for editing.")
            await print_routine(playerdata[pid]["rediting"], chan)
        else:
            await chan.send("Routine '"+words[2]+"' not found.")
    elif words[1] == "delete":
        if len(words) < 3:
            await chan.send("Please specify a routine to delete.")
            return False
        if words[2] in get_pdata(pid, "routines", {}):
            del playerdata[pid]["routines"][words[2]]
            await chan.send("Routine '"+words[2]+"' deleted.")
        else:
            await chan.send("Routine '"+words[2]+"' not found.")
    elif words[1] == "view":
        if len(words) < 3:
            await chan.send("Please specify a routine to view.")
            return False
        if words[2] in get_pdata(pid, "routines", {}):
            await print_routine(playerdata[pid]["routines"][words[2]], chan)
        else:
            await chan.send("Routine '"+words[2]+"' not found.")
    elif words[1] == "list":
        if len(get_pdata(pid, "routines", {}).keys()) == 0:
            await chan.send("You have no routines. You can create one with `!routine new`.")
        else:
            await chan.send("Your routines:\n"+", ".join(list(playerdata[pid]["routines"].keys())))
    elif words[1] == "run":
        if len(words) < 3:
            await chan.send("Please specify a routine to run.")
            return False
        for me in w.kobold_list:
            if me.d_user_id == user.id:
                break
        if len(words) > 3:
            k = find_kobold(words[3].lower(), me.get_place(), w)
        else:
            k = me
        if not k:
            await chan.send("Kobold not found.")
        elif k.nick and k != me and (not me.tribe or me.tribe.overseer != me):
            await chan.send("Can't run a routine on a named kobold unless you're the Overseer.")
        else:
            if words[2] in get_pdata(pid, "routines", {}):
                for a in playerdata[pid]["routines"][words[2]]:
                    if w == sandbox:
                        a = a.replace("!", "?")
                    m = DummyMessage(chan, user, a, w=w)
                    if not await handle_message(m):
                        await chan.send("Could not complete the routine. Aborted at action: `"+a+"`")
                        return
                await chan.send("Routine completed.")
                return True
            else:
                await chan.send("Routine '"+words[2]+"' not found.")
    elif words[1] in ["fo", "final", "finalorders", "final_orders"]:
        if len(words) < 3:
            await chan.send("Please specify a routine to use as final orders.")
            return False
        for me in w.kobold_list:
            if me.d_user_id == user.id:
                break
        if len(words) > 3:
            k = find_kobold(words[3].lower(), me.get_place(), w)
        else:
            k = me
        if not k:
            await chan.send("Kobold not found.")
        elif not k.orders and k != me:
            await chan.send("Can't set final orders for this kobold (they have orders disabled).")
        elif k != me and (not me.tribe or k.tribe != me.tribe or me.tribe.overseer != me):
            await chan.send("Only a kobold's overseer can set final orders.")
        else:
            if words[2] in get_pdata(pid, "routines", {}):
                k.fo = list(playerdata[pid]["routines"][words[2]])
                await chan.send(k.display()+"'s final orders have been set to routine '"+words[2]+"'.")
            else:
                await chan.send("Routine '"+words[2]+"' not found.")
    elif "rediting" not in playerdata[pid] or playerdata[pid]["rediting"] is None:
        await chan.send("You are not editing a routine.")
    elif words[1] == "add":
        if len(words) < 3:
            await chan.send("Please specify a command to add.")
            return False
        cmd = words[2].replace("!", "").lower()
        words = " ".join(words).split(" ", 2)
        if words[2][0] == "-":
            words[2] = words[2].replace("-", "")
        if words[2][0] != "!":
            words[2] = "!"+words[2]
        a = None
        for c in cmd_data:
            if c["cmd"] == cmd or cmd in c.get("synonyms", []):
                a = c
                break
        if a:
            if a.get("console", False) or a.get("meta", False) or not a.get("os_order", True):
                await chan.send("Can't add that command to a routine.")
                return
            playerdata[pid]["rediting"].append(words[2])
            await chan.send("Added `"+words[2]+"` to current routine.")
            await print_routine(playerdata[pid]["rediting"], chan)
        else:
            await chan.send("Command not found.")
    elif words[1] == "remove":
        s = None
        try:
            s = int(words[2])
        except:
            for a in playerdata[pid]["rediting"]:
                if a == words[2]:
                    s = playerdata[pid]["rediting"].index(a)
        if s is not None and len(playerdata[pid]["rediting"]) > s:
            rem = playerdata[pid]["rediting"].pop(s)
            await chan.send("Action "+str(s)+" (`"+rem+"`) removed from current routine.")
            await print_routine(playerdata[pid]["rediting"], chan)
        else:
            await chan.send("Action not found.")
    elif words[1] == "move":
        try:
            s = int(words[2])
        except:
            s = None
        try:
            t = int(words[3])
        except:
            t = None
        if s is not None and t is not None:
            (playerdata[pid]["rediting"][s], playerdata[pid]["rediting"][t]) = (
                playerdata[pid]["rediting"][t], playerdata[pid]["rediting"][s])
            await chan.send("Actions "+str(s)+" and "+str(t)+" swapped places.")
            await print_routine(playerdata[pid]["rediting"], chan)
        else:
            await chan.send("One or both actions not found.")
    elif words[1] == "save":
        if len(words) < 3:
            await chan.send("Please specify a name.")
            return False
        get_pdata(pid, "routines", {})
        playerdata[pid]["routines"][words[2]] = list(
            playerdata[pid]["rediting"])
        await chan.send("Routine "+words[2]+" saved.")
    elif words[1] == "close":
        playerdata[pid]["rediting"] = None
        await chan.send("Routine closed.")


async def cmd_wanderer(words, user, chan, w):
    pid = str(user.id)
    if words[1] == "list":
        wands = get_pdata(pid, "wanderers", [])
        if len(wands) == 0:
            await chan.send("You don't have any wanderers yet. You can get started on making one with `!wanderer edit`.")
        else:
            wlist = []
            for l in wands:
                d = "**"+l["nick"]+"**"
                if l["color"] == "black":
                    if l["sex"] == "male":
                        d = "<:actual_black_square:927082316675813416>"+d
                    else:
                        d = "<:actual_black_circle:927082316369641524>"+d
                else:
                    if l["sex"] == "male":
                        if l["color"] == "white":
                            shape = "large_square"
                        else:
                            shape = "square"
                    else:
                        shape = "circle"
                    d = ":"+l["color"]+"_"+shape+":"+d
                wlist.append(d)
            await chan.send("Your wanderers:\n"+", ".join(wlist))
    elif words[1] == "new":
        k = get_pdata(pid, "editing", None)
        if k:
            await chan.send("You are already editing a wanderer. Please close it first with `!wanderer close`; don't forget to `!wanderer save` first.")
            return
        await edit_wanderer(chan, user)
    elif words[1] == "edit":
        k = get_pdata(pid, "editing", None)
        if len(words) > 2:
            wands = get_pdata(pid, "wanderers", [])
            for l in wands:
                if l["nick"].lower() == words[2].lower():
                    playerdata[pid]["editing"] = dict(l)
                    break
        if not playerdata[pid]["editing"]:
            if len(words) > 2:
                await chan.send("Wanderer '"+words[2]+"' not found.")
            else:
                await chan.send("You are not editing a wanderer. Please specify the wanderer to edit, or use `!wanderer new` to create a new one.")
            return
        await edit_wanderer(chan, user)
    elif words[1] == "delete":
        wands = get_pdata(pid, "wanderers", [])
        for l in wands:
            if l["nick"].lower() == words[2].lower():
                wands.remove(l)
                await chan.send("Wanderer '"+words[2]+"' deleted.")
                return
    elif words[1] == "close":
        k = get_pdata(pid, "editing", None)
        if k:
            playerdata[pid]["editing"] = None
            await chan.send("Wanderer closed, edits discarded.")
        else:
            await chan.send("You aren't editing a wanderer.")
    elif words[1] == "join":
        for k in w.kobold_list:
            if k.d_user_id == user.id:
                await chan.send("You already have a kobold.")
                return
        wands = get_pdata(pid, "wanderers", [])
        wand = None
        for l in wands:
            if l["nick"].lower() == words[2].lower():
                wand = l
                break
        if wand:
            await cmd_name(words, user, chan, w, wand)
        else:
            await chan.send("Wanderer '"+words[2]+"' not found.")
    elif words[1] == "save":
        k = get_pdata(pid, "editing", None)
        if k:
            if len(words) < 3:
                await chan.send("Please enter a name to save this wanderer.")
                return
            playerdata[pid]["editing"]["nick"] = words[2]
            wands = get_pdata(pid, "wanderers", [])
            save = None
            for l in wands:
                if l["nick"] == words[2]:
                    save = l
                    break
            if save:
                save = dict(playerdata[pid]["editing"])
            else:
                wands.append(dict(playerdata[pid]["editing"]))
            await chan.send("Wanderer '"+words[2]+"' saved.")
        else:
            await chan.send("You aren't editing a wanderer.")


async def do_action_queue():
    toremove = []
    if not guild:
        return
    for a in action_queue:
        #console_print("Attempting action: "+a[0])
        if a[0] == "embed":
            try:
                channel = None
                if isinstance(a[1], str):
                    channel = discord.utils.get(guild.channels, name=a[1])
                else:
                    user = discord.utils.get(guild.members, id=a[1])
                    if user:
                        if not user.dm_channel:
                            channel = await user.create_dm()
                        else:
                            channel = user.dm_channel
                if channel and len(a) > 2:
                    await channel.send(None, embed=a[2])
                toremove.append(a)
            except:
                console_print("Couldn't send embed")
                await log_exception()
        if a[0] == "newchan":
            try:
                channel = discord.utils.get(guild.channels, name=a[1])
                lost = discord.utils.get(guild.roles, name="Lost Soul")
                chief = discord.utils.get(guild.roles, name="Chieftain")
                if not channel:
                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(read_messages=False),
                        guild.me: discord.PermissionOverwrite(read_messages=True),
                        lost: discord.PermissionOverwrite(send_messages=False, add_reactions=False),
                        chief: discord.PermissionOverwrite(
                            manage_messages=True, mention_everyone=True)
                    }
                    channel = await guild.create_text_channel(a[1], overwrites=overwrites)
                toremove.append(a)
            except:
                console_print("Couldn't make a channel")
                await log_exception()
        if a[0] == "delchan":
            try:
                if len(a) < 2 or time.time() > a[2]:
                    channel = discord.utils.get(guild.channels, name=a[1])
                    if channel:
                        await channel.delete()
                    toremove.append(a)
            except:
                console_print("Couldn't delete a channel")
                # await log_exception()
        if a[0] == "addrole":
            try:
                m = discord.utils.get(guild.members, id=a[2])
                if m:
                    role = discord.utils.get(guild.roles, name=a[1])
                    await m.add_roles(role)
                toremove.append(a)
            except:
                console_print("Couldn't add role to member")
                await log_exception()
        if a[0] == "delrole":
            try:
                m = discord.utils.get(guild.members, id=a[2])
                if m:
                    role = discord.utils.get(guild.roles, name=a[1])
                    await m.remove_roles(role)
                toremove.append(a)
            except:
                console_print("Couldn't add role to member")
                await log_exception()
        if a[0] == "addmember":
            try:
                m = discord.utils.get(guild.members, id=a[2])
                if m:
                    channel = discord.utils.get(guild.channels, name=a[1])
                    if channel:
                        await channel.set_permissions(m, overwrite=discord.PermissionOverwrite(read_messages=True))
                toremove.append(a)
            except:
                console_print("Couldn't add member to channel")
                await log_exception()
        if a[0] == "delmember":
            try:
                m = discord.utils.get(guild.members, id=a[2])
                if m:
                    channel = discord.utils.get(guild.channels, name=a[1])
                    if channel:
                        await channel.set_permissions(m, overwrite=discord.PermissionOverwrite(read_messages=False))
                toremove.append(a)
            except:
                console_print("Couldn't remove member from channel")
                await log_exception()
    for x in toremove:
        action_queue.remove(x)


def load_game(path='klsave'):
    refresh_data()
    global world, sandbox, playerdata, action_queue
    file = shelve.open(path, 'r')
    world = file['world']
    if 'sandbox' in file:
        sandbox = file['sandbox']
    if 'playerdata' in file:
        playerdata = file['playerdata']
    if 'action_queue' in file:
        action_queue = file['action_queue']
    file.close()
    console_print("Game loaded.")
    toremove = []
    stacked = []
    ws = [world, sandbox]
    for w in ws:
        if not hasattr(w, "did"):
            w.did = 0
        dgncount = 0
        for e in w.encounters:
            if not hasattr(e, "hostile"):
                e.hostile = True
            if not hasattr(e, "pacified"):
                e.pacified = False
            if e.place.get_tribe():
                toremove.append(e)
            if e.place in stacked:
                toremove.append(e)
            else:
                stacked.append(e.place)
            if e.place.dungeon:
                dgncount += 1
            for c in e.creatures:
                if not hasattr(c, "guardian"):
                    c.guardian = None
                if isinstance(c, Kobold):
                    c.encounter = e
                else:
                    for j in creature_data:
                        if j["name"] == c.basename:
                            c.products = list(j.get("products", []))
            broremove = []
            for p in e.engaged:
                if not p.owner:
                    broremove.append(p)
                    continue
                console_print("Engagement of "+p.owner.get_name()+"'s party with " +
                              e.creatures[0].name+str((e.place.x, e.place.y, e.place.z)))
                for k in p.k_members:
                    console_print("Member "+k.get_name() +
                                  " at "+str((k.x, k.y, k.z)))
                    if k.x != e.place.x or k.y != e.place.y:
                        console_print(
                            "Mismatched encounter/engagement location found, removing")
                        if p not in broremove:
                            broremove.append(p)
            for b in broremove:
                e.engaged.remove(b)
        for e in toremove:
            w.encounters.remove(e)
        console_print("Dungeon encounter count: "+str(dgncount))
        allitems = []
        tribolds = {}
        for k in w.kobold_list:
            if not hasattr(k, "worns"):
                k.worns = {"body": k.worn, "head": None, "acc": None}
                if k.worn and k.worn in k.items:
                    k.items.remove(k.worn)
            if k.hp > 0 and k.tribe:
                if str(k.tribe.id) not in tribolds:
                    tribolds[str(k.tribe.id)] = 0
                tribolds[str(k.tribe.id)] += 1
                if k in k.tribe.tavern:
                    k.tribe.tavern.remove(k)
            for i in k.items:
                allitems.append(i)
            if k.party:
                p = k.party
                if k.has_trait("bound") and k not in p.owner.tribe.prison:
                    p.owner.tribe.prison.append(k)
                if p.owner:
                    leader = p.owner.get_name()
                else:
                    leader = "none"
                #console_print(k.get_name()+" is in party "+str(p.id)+" with leader "+leader)
                mem = list(p.k_members)
                for c in p.c_members:
                    if not hasattr(c, "products"):
                        c.products = []
                if not p.owner:
                    p.owner = mem[0]
                for l in mem:
                    if l.x != p.owner.x or l.y != p.owner.y:
                        console_print("joining everyone together")
                        l.x = p.owner.x
                        l.y = p.owner.y
                    if l.party != p:
                        p.members.remove(l)
                if leader == "none":
                    console_print("fixing")
                    for m in p.members:
                        p.leave(m)
        for t in w.tribes:
            if t.name == "Unnamed Tribe":
                t.name = tribe_name()
            if not hasattr(t, "kennel_items"):
                t.kennel_items = []
            for i in t.items:
                allitems.append(i)
            for task in t.tasks:
                if len(task) < 5:
                    task.append(True)
            newbolds = []
            newboldnames = []
            for k in t.kobolds:
                if k.hp > 0 and k.get_place() == t and (k.tribe == t or k in t.prison) and k not in newbolds:
                    newbolds.append(k)
                    newboldnames.append(k.get_name())
            t.kobolds = newbolds
            console_print("tribe "+str(t.id) +
                          str((t.x, t.y, t.z))+": "+str(newboldnames))
            if str(t.id) in tribolds:
                console_print("Tribe "+str(t.id)+" has " +
                              str(tribolds[str(t.id)])+" left in the world")
        for m in w.map:
            for i in w.map[m].items:
                allitems.append(i)
            if not hasattr(w.map[m], "pasture"):
                w.map[m].pasture = []
        df = {}
        for j in item_data:
            if j["name"] == "Default":
                df = j
        eggs = 0
        for i in allitems:
            this = {}
            if i.name == "Kobold Egg":
                eggs += 1
            for j in item_data:
                if j["name"] == i.name:
                    this = j
            for d in df:
                if not hasattr(i, d):
                    setattr(i, d, this.get(d, df[d]))
        console_print("there are "+str(eggs)+" eggs that will be bugged")


def save_game(path='klsave'):
    file = shelve.open(path, 'n')
    file['world'] = world
    file['sandbox'] = sandbox
    file['playerdata'] = playerdata
    file['action_queue'] = action_queue
    file.close()
    #console_print("Game saved.")


def get_pdata(id, data, df=None):
    global playerdata
    i = str(id)
    if i not in playerdata:
        playerdata[i] = {}
    if data not in playerdata[i]:
        playerdata[i][data] = df
    return playerdata[i][data]


def refresh_data():
    global item_data, item_cats, research_data, building_data, craft_data, cmd_data, creature_data, spell_data, liquid_data, landmark_data, trait_data, skill_data, dungeon_data
    item_data = get_json('data/items.json')
    item_cats = {}
    d = None
    for i in item_data:
        if i["name"] == "Default":
            d = i
        else:
            if i.get("cat", None):
                for c in i["cat"]:
                    if c not in item_cats:
                        item_cats[c] = []
                    item_cats[c].append(i["name"])
            for prop in i:
                if prop not in d:
                    console_print(
                        "WARNING: Property "+prop+" found on item "+i["name"]+" does not have a default")
    # console_print(item_cats)
    research_data = get_json('data/research.json')
    building_data = get_json('data/buildings.json')
    craft_data = get_json('data/crafts.json')
    cmd_data = get_json('data/commands.json')
    creature_data = get_json('data/creatures.json')
    for i in creature_data:
        if i["name"] == "Default":
            d = i
        else:
            for prop in i:
                if prop not in d:
                    console_print(
                        "WARNING: Property "+prop+" found on creature "+i["name"]+" does not have a default")
    spell_data = get_json('data/spells.json')
    liquid_data = get_json('data/liquids.json')
    landmark_data = get_json('data/landmarks.json')
    trait_data = get_json('data/traits.json')
    skill_data = get_json('data/skills.json')
    dungeon_data = get_json('data/dungeons.json')


async def handle_final_orders(w):
    for k in w.kobold_list:
        if len(k.fo) > 0:
            console_print("handling final orders for "+k.get_name())
            for a in k.fo:
                cmd = a.split()[0]
                cmd = cmd.replace("!", "").lower()
                cmd = cmd.replace("-", "").lower()
                act = None
                for c in cmd_data:
                    if c["cmd"] == cmd or cmd in c.get("synonyms", []):
                        act = c
                        break
                if act and k.ap >= act.get("cost", 0):
                    m = DummyMessage(discord.utils.get(
                        guild.channels, name=k.get_chan()), None, a, w=w, k=k)
                    await handle_message(m)
        k.fo = []


async def cmd_task_test(words, user, chan, w):
    await handle_tasks(w)


async def handle_tasks(w):
    for t in w.tribes:
        tile = w.get_tile(t.x, t.y, t.z)
        console_print("handling tasks for tribe "+t.name+" (ID "+str(t.id)+")")
        for d in t.tasks:
            words = d[0].split()
            cmd = words[0]
            cmd = cmd.replace("!", "").lower()
            cmd = cmd.replace("-", "").lower()
            act = None
            for c in cmd_data:
                if c["cmd"] == cmd or cmd in c.get("synonyms", []):
                    act = c
                    break
            if act:
                bolds = list(t.kobolds)
                t.justbuilt = "&"
                times = 0
                toolsused = []
                lastworker = None
                while True:
                    if len(bolds) == 0:
                        break
                    worker = None
                    best = -10
                    bs = list(bolds)
                    console_print(
                        "looking through kobolds for workers, task "+cmd)
                    for k in bs:
                        if not k.orders or k.has_trait("resting"):
                            continue
                        if act.get("min_age", 6) > k.age:
                            continue
                        if k.ap < act.get("cost", 0) and not k.has_trait("fasting") and not k.has_trait("fed"):
                            k.auto_eat()
                        if cmd in ["research", "build"] and k == lastworker:
                            continue
                        if k.ap >= act.get("cost", 0):
                            if not act.get("skill", None) or k.skmod(act["skill"])+k.smod(skill_data[act["skill"]]["stat"]) > best:
                                if act.get("skill", None):
                                    best = k.skmod(
                                        act["skill"])+k.smod(skill_data[act["skill"]]["stat"])
                                worker = k
                        else:
                            bolds.remove(k)
                    if not worker and lastworker in bolds:
                        console_print("no worker, defaulting to last worker")
                        worker = lastworker
                    if worker:
                        console_print("worker found: "+worker.get_name())
                        if act.get("tool", None) and d[4]:
                            tool = None
                            besti = 0
                            if not worker.shaded:
                                umb = True
                            else:
                                umb = False
                            for i in t.items+toolsused:
                                if i.tool == act["tool"] and i.toolpower >= besti and i.place:
                                    tool = i
                                    besti = i.toolpower
                                elif i.name == "Silk Parasol" and umb and not tool:
                                    tool = i
                            if tool and tool.place != worker:
                                if tool in toolsused and isinstance(tool.place, Kobold):
                                    cmd_drop([], tool.place, tool)
                                if len(worker.items) >= worker.inv_size:
                                    cmd_drop([], worker, choice(worker.items))
                                cmd_get([], worker, tool)
                                if tool not in toolsused:
                                    toolsused.append(tool)
                        sung = None
                        if not worker.shaded:
                            if lastworker and lastworker != worker and lastworker.has_trait("sunglasses"):
                                cmd_unshade([], lastworker, None)
                                for i in lastworker.items:
                                    if i.name == "Sunglasses":
                                        cmd_drop([], worker, i)
                                        break
                            for i in list(t.items+worker.items):
                                if i.name == "Sunglasses":
                                    sung = i
                            if sung:
                                sung.use(worker)
                        m = DummyMessage(discord.utils.get(
                            guild.channels, name=worker.get_chan()), None, d[0], w=w, k=worker)
                        lastworker = worker
                        if not await handle_message(m):
                            console_print(
                                "action failed, trying to remove worker")
                            if worker in bolds:
                                bolds.remove(worker)
                    else:
                        break
                    times += 1
                    try:
                        if d[1]:
                            if d[1] == "times" and times >= int(d[2]):
                                break
                            elif hasattr(t, d[1]) and isinstance(getattr(t, d[1]), int) and getattr(t, d[1]) >= int(d[2]):
                                break
                            elif d[1] == "farm_prog" and d[3] in tile.farming_prog and tile.farming_prog[d[3]] >= int(d[2]):
                                break
                            elif d[1] == "farm_cap" and tile.farm_cap >= int(d[2]):
                                break
                            elif d[1] == "items" and t.has_item(d[3], int(d[2])):
                                break
                        if len(words) > 1 and words[1].lower() in t.justbuilt.lower():
                            b = {}
                            if "build" in cmd:
                                b = find_building(t.justbuilt)
                            elif "research" in cmd:
                                b = find_research(t.justbuilt)
                            elif "dom" in cmd or "farm" in cmd or "craft" in cmd:
                                break
                            else:
                                console_print(
                                    "We seem to have just built a thing that doesn't exist: "+str(t.justbuilt))
                            if not b.get("repeatable", False):
                                break
                        if "expand" in cmd and tile.farm_cap >= 1000:
                            break
                    except:
                        await log_exception("Task for tribe "+str(t.id)+": `"+cmd+"`")
                        break
                for i in toolsused:
                    if isinstance(i.place, Kobold):
                        cmd_drop([], i.place, i)


async def main_loop():
    astimer = 0
    while True:
        await asyncio.sleep(1)
        sta = False
        try:
            await do_msg_queue()
            await do_post_queue()
            await do_action_queue()
            astimer += 1
            if astimer >= 60:
                save_game()
                astimer = 0
                if time.time() > world.next_mc_time:
                    save_game("backup/klsave")
                    world.next_mc_time += 86400
                    sta = True
                    await handle_final_orders(world)
                    await handle_tasks(world)
                    world.month_change()
        except:
            await log_exception()
            if sta:
                for t in world.tribes:
                    game_print("Error: Something went wrong during month change. The previous logs are not canon. The dev has been notified; please wait for him to fix the problem and revert to the backup.", t.get_chan())

console_queue = []
action_queue = []
post_queue = {}
world = World()
sandbox = World()
playerdata = {}
console_crosspost = True

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILDN = os.getenv('DISCORD_GUILD')
guild = None

intents = discord.Intents.all()
clive = discord.Client(intents=intents)


async def cmd_verify(words, member, chan, w):
    role = discord.utils.get(guild.roles, name="Verified")
    await member.add_roles(role)
    action_queue.append(["addrole", "Lost Soul", member.id])
    newchan = discord.utils.get(member.guild.channels, name="general")
    await newchan.send("<@!"+str(member.id)+"> Welcome! Make yourself at home, be sure to have a look at the <#918263140100239381> and <#918268315980402698>, and type `!join` in any channel when you're ready to join!")
    return True


@clive.event
async def on_ready():
    global guild
    for g in clive.guilds:
        if g.name == GUILDN:
            guild = g
            break
    console_print(
        f'{clive.user} is connected to the following guild:\n'
        f'{guild.name}(id: {guild.id})'
    )
    game = discord.Game("Kobold Legacy")
    await clive.change_presence(activity=game)


@clive.event
async def on_member_join(member):
    newchan = discord.utils.get(member.guild.channels, name="verify")
    await newchan.send("<@!"+str(member.id)+"> Hey! Before you can begin your legacy, you need to let me know you're a real person by typing `!verify` in the chat here. If that doesn't work or something is wrong, please ping/DM the dev (orange name).")


@clive.event
async def on_member_remove(member):
    for k in world.kobold_list:
        if k.d_user_id == member.id:
            cmd_quit([], k, None, force=True)
    newchan = discord.utils.get(member.guild.channels, name="general")
    await newchan.send(member.name+" suffered an identity crisis and left this world.")


@clive.event
async def on_message(message):
    if message.author == clive.user:
        return
    test = message.content.replace("-", "!")
    test = test.replace("?", "!")
    test = test.replace(">", "!")
    teest = test.split("!")
    try:
        num = int(teest[0])
        message.content = message.content.replace(str(num), "", 1)
    except:
        num = 1
    me = None
    allmembers = [None]
    if ">party " in message.content.lower():
        global world, sandbox
        if "?" in message.content:
            w = sandbox
        else:
            w = world
        for k in w.kobold_list:
            if k.d_user_id == message.author.id:
                me = k
                break
        if me.party and me.party.owner == me:
            allmembers = list(me.party.members)
            message.content = message.content.lower().replace(">party ", "")
            if message.content[0] not in ["!", "-", "?"]:
                if w == world:
                    message.content = "!"+message.content
                else:
                    message.content = "?"+message.content
        else:
            message.channel.send("You are not the leader of a party.")
            return
    omc = str(message.content)
    if num > 0 and num <= 12:
        for x in range(num):
            gewd = True
            for k in allmembers:
                message.content = str(omc)
                if k != me:
                    message.content = ">"+k.get_name()+" "+message.content
                good = await handle_message(message, num)
                if not good:
                    gewd = False
            if not gewd:
                break


async def handle_message(message, num=1):
    chan = message.channel
    try:
        global world, sandbox
        if message.author == clive.user:
            return
        if len(message.content) <= 0:
            return
        user = message.author
        words = message.content.split()
        words[0] = words[0].lower()
        if user:
            cname = getattr(chan, "name", user.id)
            if cname == user.id:
                user = discord.utils.get(guild.members, id=user.id)
            w = world
            if words[0] == "!d":
                return
            if ("?" in words[0] or (">" in words[0] and len(words) > 1 and "?" in words[1])):
                sp = discord.utils.get(guild.roles, name="Sandbox person")
                if sp in user.roles:
                    message.content = message.content.replace("?", "!")
                    for x in range(len(words)):
                        words[x] = words[x].replace("?", "!")
                    w = sandbox
        else:
            w = message.world
            if message.channel:
                cname = message.channel.name
            else:
                cname = "final-orders-party"
        me = None
        superforce = False
        if "$" in words[0] and cname == "console":
            k = find_kobold(words[0].replace("$", "").lower(), None, w)
            if not k:
                await chan.send("Kobold not found. Make sure you've spelled their name correctly.")
                return
            else:
                me = k
            words.pop(0)
            message.content = " ".join(words)
            superforce = True
        else:
            if user:
                for k in w.kobold_list:
                    if k.d_user_id == user.id:
                        me = k
                        break
            else:
                me = message.k
        repeat = False
        if me:
            place = me.get_place()
            dumb = me
            if message.content == "^":
                if time.time()-me.lasttime < 60:
                    message.content = me.lastcommand
                    words = message.content.split()
                    words[0] = words[0].lower()
                    repeat = True
            elif message.content == me.lastcommand:
                repeat = True
            if message.content[0] in [">", "!", "-"]:
                me.lastcommand = message.content
        ordering = False
        if message.content[0] == ">" and (">!" in words[0] or "> !" in message.content or ">-" in words[0] or "> -" in message.content):
            if words[0] != ">":
                words.insert(1, words[0].replace(">", ""))
            words[0] = ">"+me.lastfollower
        # ordering another kobold
        if message.content[0] == ">" and cname != user.id and ("tribe" in cname or "party" in cname):
            s = words[0].replace(">", "").lower()
            k = find_kobold(s, place, w)
            if not k:
                k = find_creature_i(s, me)
                if not k:
                    await chan.send("Kobold/creature '"+s+"' not found. Make sure you've spelled their name correctly and they're in the same area as you.")
                    return
            if k.nick:
                if not me.tribe or not k.tribe or (not k.tribe.overseer == me and (not k.party or k.party != me.party or me.party.owner != me or isinstance(place, Tribe))):
                    await chan.send("You can only order a named kobold under the following conditions: you must be the Overseer, or you must be the leader of that kobold's party and in the overworld.")
                    return
                elif not k.orders and not k.has_trait("inactive"):
                    await chan.send("That player has opted out of allowing Overseer/Party leader commands.")
                    return
            if not isinstance(k, Creature):
                if me.tribe and k not in me.tribe.prison:
                    if not k.tribe and k.party != me.party:
                        await chan.send("Can't command a tribeless kobold, unless they are a prisoner.")
                        return
                    if k.tribe != me.tribe and (not me.party or k not in me.party.members):
                        await chan.send("Can't command a kobold from another tribe.")
                        return
                if k.has_trait("bound") and not k.has_trait("broken"):
                    await chan.send("The prisoner will not follow your orders until their will has been broken.")
                    return
            oldme = me
            me.lastfollower = k.get_name()
            k.commandedby = me
            me = k
            ordering = True
            words.pop(0)
            message.content = " ".join(words)
        if len(words) == 0:
            return  # clearly not a command
        if ordering and words[0][0] not in ["!", "-"]:
            words[0] = "!"+words[0]
        # this is a command
        if words[0][0] == "!" or (words[0][0] == "-" and cname != "changelog"):
            cmd = words[0].replace("!", "").lower()
            cmd = cmd.replace("-", "").lower()
            if len(cmd) == 0:
                return
            a = None
            for c in cmd_data:
                if c["cmd"] == cmd or cmd in c.get("synonyms", []):
                    a = c
                    break
            if a:
                argsneeded = a.get("args", 1)-a.get("args_optional", 0)
                meta = a.get("meta", False)
                console = a.get("console", False)
                free = a.get("free", False)
                engage = None
                if me and not console and not meta:
                    for e in w.encounters:
                        if me.party and me.party in e.engaged:
                            if not free and me.didturn:
                                await chan.send(me.display()+" has already used their action for this combat round.")
                                return
                            engage = e
                            break
                bwcheck = False
                if len(words)-1 < argsneeded and not console:
                    await chan.send("Command usage:\n"+a["desc"])
                elif console and "console" not in chan.name:
                    await chan.send("This command can only be done in console.")
                elif meta and ordering:
                    await chan.send("Cannot order a nameless kobold to do meta commands.")
                elif not console and not meta and not superforce:
                    if user and (cname == user.id or ("tribe" not in cname and "party" not in cname)):
                        return  # ignore channels that aren't game channels
                    elif not me:
                        await chan.send("You do not have a kobold in this world.")
                    elif ordering and not a.get("nameless", True):
                        await chan.send("A kobold cannot be ordered to do this.")
                    elif ordering and isinstance(me, Kobold) and me.age < a.get("min_age", 6):
                        await chan.send("This kobold is too young to do that.")
                    elif ordering and me.nick and (time.time()-me.lasttime < 300 or a.get("cost", 0) > 0 or a.get("cp", 0) > 0) and not me.has_trait("inactive"):
                        await chan.send("When ordering an active named kobold, you cannot issue a command that costs AP/mana, or any command within 5 minutes of that player's last command.")
                    elif ordering and isinstance(me, Kobold) and a.get("command_by", None) and getattr(me.tribe, a["command_by"], None) != oldme:
                        await chan.send("Only the "+a["command_by"]+" can order a nameless kobold to do this.")
                    elif ordering and me.nick and not a.get("os_order", True):
                        await chan.send("Cannot order a named kobold to do that.")
                    elif ordering and isinstance(me, Creature) and (a.get("animal_training", None) and a["animal_training"] not in me.training and a["animal_training"] != "any" and me.stats["int"] < 6):
                        await chan.send("This creature needs "+a["animal_training"]+" training to do that.")
                    elif ordering and isinstance(me, Creature) and a.get("animal_training", None) is None:
                        await chan.send("A creature cannot be ordered to do this.")
                    elif a.get("chieftain", False) and isinstance(me, Kobold) and (not me.tribe or me.tribe.chieftain != me or ordering):
                        await chan.send("Only the chieftain can do this.")
                    elif a.get("overseer", False) and isinstance(me, Kobold) and (not me.tribe or (me.tribe.overseer and me.tribe.overseer != me) or ordering):
                        await chan.send("Only the overseer can do this.")
                    elif not a.get("anywhere", False) and not a.get("overworld", False) and ("tribe" not in me.get_chan() or me in place.tavern):
                        await chan.send("This action cannot be performed in the overworld, or in another tribe's tavern.")
                    elif isinstance(place, Tribe) and me in place.tavern and not a.get("tavern", True):
                        await chan.send("This action cannot be performed in another tribe's tavern.")
                    elif "tribe" not in cname and "party" not in cname:
                        await chan.send("This action must be done from a game channel.")
                    elif a.get("overworld", False) and isinstance(place, Tribe):
                        await chan.send("This action must be done in the overworld.")
                    elif a.get("party_leader", False) and (not me.party or me.party.owner != me):
                        await chan.send("Only a party leader can perform this action.")
                    elif not free and me.has_trait("carried"):
                        await chan.send("You can't do that while you're being carried.")
                    elif not a.get("carry", True) and (me.carry or me.has_trait("carried")):
                        await chan.send("You can't do that while you're carrying someone or being carried.")
                    elif not a.get("dungeon", True) and me.dungeon:
                        await chan.send("You can't do that in a dungeon.")
                    elif not user and me.hp <= a.get("danger", 0):
                        await chan.send("This command is too dangerous to run automatically at the kobold's current health.")
                    elif a.get("informational", False) and not a.get("allow_multi", False) and num > 1:
                        await chan.send("This command cannot be repeated.")
                    elif ordering and (a.get("cost", 0) > 0 or a.get("cp", 0) > 0) and oldme.cp < a.get("cp", 1) and me.age >= 6:
                        await chan.send("You don't have enough CP to command a kobold to do this. (have "+str(oldme.cp)+", need "+str(a.get("cp", 1))+")")
                    else:
                        if engage and not a.get("combat", True):
                            await chan.send("That command cannot be done in combat.")
                            return
                        if isinstance(place, Tribe) and me in place.prison:
                            t = place
                        elif isinstance(me, Kobold):
                            t = me.tribe
                        else:
                            t = oldme.tribe
                        good = check_req(t, a.get("req", []), me)
                        if good != "good":
                            await chan.send("Can't use this command: "+good)
                        else:
                            bwcheck = True
                else:
                    bwcheck = True
                if not bwcheck:
                    return
                args = message.content.split(" ", a.get("args", 1))
                targ = a.get("target", None)
                target = None
                num = 0
                if a["cmd"] == "use" and not user:
                    words[len(words)-1] += " -first"
                if targ == "living":
                    s = args[a.get("targ_arg", len(args)-1)].lower()
                    if len(args) <= 1 and a.get("target_self_if_omitted", False):
                        target = me
                    elif s in ["self", "me", "myself"]:
                        target = me
                    elif s in ["anyone", "someone", "any", "low", "lowest", "lowhealth", "lowhp"]:
                        bolds = []
                        for k in w.kobold_list:
                            if "low" in s and k.hp == k.max_hp:
                                continue
                            if k.get_place() == place:
                                bolds.append(k)
                        target = choice(bolds)
                    else:
                        target = find_kobold(s, place, w)
                    if not target:
                        target = find_creature_i(s, me)
                    if not target:
                        await chan.send("Kobold/Creature '"+s+"' not found.")
                        return
                    if target == me and not a.get("can_target_self", False):
                        await chan.send("Cannot target self with that command.")
                        return
                if targ == "creature":
                    s = args[a.get("targ_arg", len(args)-1)].lower()
                    target = find_creature_i(s, me)
                    if not target:
                        await chan.send("Creature '"+s+"' not found.")
                        return
                if targ == "kobold":
                    s = args[a.get("targ_arg", len(args)-1)].lower()
                    if len(args) <= 1 and a.get("target_self_if_omitted", False):
                        target = me
                    elif s in ["self", "me", "myself"]:
                        target = me
                    elif s in ["anyone", "someone", "any", "low", "lowest", "lowhealth", "lowhp"]:
                        bolds = []
                        for k in w.kobold_list:
                            if k.hp == k.max_hp:
                                continue
                            if k.get_place() == place:
                                bolds.append(k)
                        target = choice(bolds)
                    else:
                        target = find_kobold(s, place, w)
                    if not target:
                        await chan.send("Kobold '"+s+"' not found.")
                        return
                    if target == me and not a.get("can_target_self", False):
                        await chan.send("Cannot target self with that command.")
                        return
                if targ == "item":
                    search = args[a.get("targ_arg", len(args)-1)]
                    if a.get("numbers", False):
                        wordwords = search.split()
                        for b in wordwords:
                            try:
                                num = int(b)
                            except:
                                pass
                            if num > 0:
                                wordwords.remove(b)
                                break
                        search = " ".join(wordwords)
                    if user:
                        target = await multi_select(chan, search, me, a.get("start_in_inv", True), a.get("place", "any"), a.get("target_type", None), ordering=ordering)
                    else:
                        targets = find_item_multi(search.lower(), me, a.get(
                            "start_in_inv", True), a.get("place", "any"), a.get("target_type", None))
                        if targets:
                            target = targets[0]
                    if not target:
                        return
                if targ == "enemy":
                    if engage:
                        if len(engage.creatures) == 1:
                            target = engage.creatures[0]
                        for c in engage.creatures:
                            if isinstance(c, Kobold) or not c.name[-1].isupper():
                                if args[a.get("targ_arg", len(args)-1)].lower() in c.get_name().lower():
                                    target = c
                            else:
                                if args[a.get("targ_arg", len(args)-1)].lower() == c.name[-1].lower():
                                    target = c
                        if not target:
                            await chan.send("Use the letter corresponding to the target you want. (A, B, C)")
                            return
                    else:
                        await chan.send("That command can only be done in combat.")
                        return
                if a.get("combatonly", False) and not engage:
                    await chan.send("That command can only be done in combat.")
                    return
                cost = a.get("cost", 0)
                if cost > 0 and me.ap < cost:
                    await chan.send("Not enough AP. (have "+str(me.ap)+", need "+str(cost)+")")
                    return
                sp = a.get("sp", 0)
                if sp > 0:
                    havesp = get_pdata(user.id, "sp", 10)
                    if havesp < sp:
                        await chan.send("Not enough SP. (have "+str(havesp)+", need "+str(sp)+")")
                        return
                if num > 0:
                    args.append(num)
                if user:
                    if a.get("confirm_prompt", None):
                        if not await confirm_prompt(chan, a["confirm_prompt"], user):
                            await chan.send("Action aborted.")
                            return
                    elif me and me.hp <= a.get("danger", 0):
                        if not await confirm_prompt(chan, "This action could potentially kill "+me.display()+" at their current HP. Proceed anyway?", user):
                            await chan.send("Action aborted.")
                            return
                    elif me and me.has_trait("tool_broke"):
                        me.del_trait("tool_broke")
                        if not await confirm_prompt(chan, me.display()+"'s tool broke recently. Proceed anyway?", user):
                            await chan.send("Action aborted.")
                            return
                if a.get("informational", False):
                    done = await globals()[a.get("function", "sorry nothing")](args, me, chan)
                elif a.get("async", False):
                    done = await globals()[a.get("function", "sorry nothing")](args, me, target)
                elif meta or console:
                    done = await globals()[a.get("function", "sorry nothing")](args, user, chan, w)
                else:
                    done = globals()[a.get("function", "sorry nothing")](
                        args, me, target)
                if done and me:
                    if user:
                        dumb.lasttime = time.time()
                        if not ordering:
                            me.del_trait("inactive")
                    if cost > 0 or a.get("cp", 0) > 0:
                        me.ap_tax(cost)
                        if ordering and me.age >= 6:
                            oldme.cp -= a.get("cp", 1)
                            oldme.gain_xp("command", a.get("cp", 1)*10)
                    if sp > 0:
                        playerdata[str(user.id)]["sp"] -= sp
                        await chan.send(str(sp)+" SP spent. (remaining: "+str(havesp-sp)+")")
                    place = me.get_place()  # in case this action moved you
                    if not console and not meta and not isinstance(place, Tribe):
                        if not free:
                            for e in w.encounters:
                                if e.hostile and e.place == place and me.party and me.party not in e.engaged:
                                    me.party.stealth_roll(e, me=me, aps=cost)
                        if engage and me.party in engage.engaged:
                            if not free:
                                if me.has_trait("haste"):
                                    me.del_trait("haste")
                                else:
                                    me.didturn = True
                            alldone = True
                            for k in me.party.members:
                                if not k.didturn:
                                    alldone = False
                            if alldone:
                                engage.enemy_turn(me.party)
                    try:
                        await message.delete()
                    except:
                        pass
                    return True
            else:
                await chan.send("Command not found.")
                return
    except:
        if chan:
            await chan.send("Your command resulted in an error. The dev has been notified.")
        if user:
            await log_exception("Player: "+str(user)+", channel: "+str(cname)+", command: `"+message.content+"`")
        else:
            await log_exception("Player: "+me.get_name()+", channel: "+str(cname)+", command: `"+message.content+"` (final orders)")

try:
    load_game()
except:
    console_print("There was a problem running load_game")
    m = traceback.format_exc().split("\n")
    console_print(m)

clive.loop.create_task(main_loop())
clive.run(TOKEN)
