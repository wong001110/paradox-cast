from app.database import Base, engine
from app.models import CharacterCard, Credential, User, Visibility
from app.schemas import CharacterCreate
from sqlalchemy.orm import Session

def test_character_card_is_adult_and_identity_only() -> None:
    assert CharacterCreate(name="Hana", adult_age=21).adult_age == 21
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    with Session(engine) as session:
        user=User(display_name="Director"); session.add(user); session.flush()
        card=CharacterCard(owner_id=user.id,name="Hana",adult_age=21,profile={"values":["empathy"]},visibility=Visibility.PRIVATE); session.add(card); session.commit()
        assert session.get(CharacterCard,card.id).profile["values"] == ["empathy"]

def test_credential_model_has_no_plaintext_export_field() -> None:
    assert "api_secret" not in Credential.__table__.columns
    assert "secret_ciphertext" in Credential.__table__.columns
