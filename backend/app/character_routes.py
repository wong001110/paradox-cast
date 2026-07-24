from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from .database import get_session
from .models import CharacterCard, Visibility
from .schemas import CharacterCreate

router = APIRouter(prefix="/api/characters", tags=["characters"])

def view(card: CharacterCard) -> dict:
    return {"id":card.id,"name":card.name,"adult_age":card.adult_age,"biography":card.biography,"profile":card.profile,"visual_assets":card.visual_assets,"visibility":card.visibility.value,"version":card.version,"forked_from_id":card.forked_from_id}

@router.post("", status_code=201)
def create(payload: CharacterCreate, owner_id: str, session: Session=Depends(get_session)) -> dict:
    card=CharacterCard(owner_id=owner_id, **payload.model_dump()); session.add(card); session.commit(); session.refresh(card); return view(card)

@router.get("")
def list_cards(owner_id: str, session: Session=Depends(get_session)) -> list[dict]:
    return [view(card) for card in session.query(CharacterCard).filter_by(owner_id=owner_id).all()]

@router.get("/{card_id}")
def get_card(card_id: str, session: Session=Depends(get_session)) -> dict:
    card=session.get(CharacterCard,card_id)
    if not card: raise HTTPException(404,"character not found")
    return view(card)

@router.put("/{card_id}")
def update(card_id: str, payload: CharacterCreate, owner_id: str, session: Session=Depends(get_session)) -> dict:
    card=session.get(CharacterCard,card_id)
    if not card or card.owner_id != owner_id: raise HTTPException(404,"character not found")
    for key,value in payload.model_dump().items(): setattr(card,key,value)
    card.version += 1; session.commit(); return view(card)

@router.delete("/{card_id}", status_code=204)
def delete(card_id: str, owner_id: str, session: Session=Depends(get_session)) -> Response:
    card=session.get(CharacterCard,card_id)
    if not card or card.owner_id != owner_id: raise HTTPException(404,"character not found")
    session.delete(card); session.commit(); return Response(status_code=204)

@router.post("/{card_id}/duplicate", status_code=201)
def duplicate(card_id: str, owner_id: str, session: Session=Depends(get_session)) -> dict:
    source=session.get(CharacterCard,card_id)
    if not source: raise HTTPException(404,"character not found")
    copy=CharacterCard(owner_id=owner_id,name=f"{source.name} (Copy)",adult_age=source.adult_age,biography=source.biography,profile=source.profile,visual_assets=source.visual_assets,visibility=Visibility.PRIVATE,forked_from_id=source.id)
    session.add(copy); session.commit(); session.refresh(copy); return view(copy)

@router.get("/{card_id}/export")
def export(card_id: str, session: Session=Depends(get_session)) -> dict:
    return {"format":"paradox-cast-character/v1","character":get_card(card_id,session)}

@router.post("/import", status_code=201)
def import_card(payload: dict, owner_id: str, session: Session=Depends(get_session)) -> dict:
    source=payload.get("character",payload)
    allowed={key:source.get(key) for key in ("name","adult_age","biography","profile","visual_assets","visibility")}
    data=CharacterCreate(**allowed).model_dump(); data["visibility"]=Visibility.PRIVATE
    card=CharacterCard(owner_id=owner_id,forked_from_id=source.get("id"),**data); session.add(card); session.commit(); session.refresh(card); return view(card)

@router.get("/share/{card_id}")
def shared(card_id: str, session: Session=Depends(get_session)) -> dict:
    card=session.get(CharacterCard,card_id)
    if not card or card.visibility is Visibility.PRIVATE: raise HTTPException(404,"shared character not found")
    return {"share_type":"fork","character":view(card)}
