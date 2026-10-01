from cards.fonts import load_font
"""Cookie-free overview cards; no fabricated seasonal or personal records."""
from io import BytesIO
from PIL import ImageDraw,ImageFont
from config import BASE_DIR
from cards.dashboard_theme import dashboard_background,panel
INFO={
 "abyss":("Spiral Abyss",(168,123,255),[("Challenge","Progress through floors and chambers, completing combat objectives."),("Preparation","Prepare separate teams for chambers with two halves."),("Personal report","Your stars, battle history and teams require HoYoLAB authentication.")]),
 "stygian":("Stygian Onslaught",(99,214,224),[("Challenge","Fight boss encounters and improve your clear times."),("Preparation","Build teams around the enemies and selected difficulty."),("Personal report","Your teams, clear times and damage records require HoYoLAB authentication.")]),
 "theater":("Imaginarium Theater",(224,181,112),[("Challenge","Complete a sequence of combat acts with a rotating cast."),("Preparation","Check the current cast restrictions and available supporting characters."),("Personal report","Your acts, medals and battle honours require HoYoLAB authentication.")])}
def event_info_card(command,reason):
    key="abyss" if command in ("abyss","abyssinfo") else "stygian" if command=="stygian" else "theater"
    title,color,sections=INFO[key]
    image=dashboard_background(1400,850);draw=ImageDraw.Draw(image)
    path=str(BASE_DIR/"assets/fonts/Genshin_Impact.ttf")
    def text(value,xy,size=24,fill=(232,234,240)):
        draw.text(xy,value,font=load_font(path,size),fill=fill)
    text(title,(50,35),40,color);text("EVENT OVERVIEW • NO LOGIN REQUIRED",(50,100),20,color)
    def wrap(value,x,y,width=1230):
        font=load_font(path,23);line=""
        for word in value.split():
            candidate=(line+" "+word).strip()
            if font.getlength(candidate)>width:
                text(line,(x,y),23);y+=34;line=word
            else:line=candidate
        text(line,(x,y),23)
    for index,(label,detail) in enumerate(sections):
        y=160+index*150;panel(draw,(40,y,1360,y+130));text(label,(65,y+15),26,color);wrap(detail,65,y+57)
    wrap(reason,50,635)
    text("Use /cookie_login privately to restore your personal reports.",(50,725),21,color)
    text("General guide • Current enemies, dates and rewards are not verified here.",(50,780),19)
    buffer=BytesIO();image.convert("RGB").save(buffer,format="JPEG",quality=92);buffer.seek(0);buffer.name=f"{key}_overview.jpg"
    return buffer,title+" • Event overview"
