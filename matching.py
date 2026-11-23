import re
from sqlalchemy import select
from .models import Lead

def normalize_quantity(value):
    if not value: return None
    m=re.search(r'(\d+(?:\.\d+)?)\s*(kg|kgs|kilograms?|qtl|quintals?|mt|tonnes?|tons?)\b',value.lower())
    if not m: return None
    amount=float(m.group(1)); unit=m.group(2)
    factor=1 if unit.startswith('kg') or unit.startswith('kilo') else 100 if unit.startswith(('qtl','quintal')) else 1000
    return amount*factor

def score_matches(db,buyer):
    if buyer.kind!='buyer': return []
    suppliers=db.scalars(select(Lead).where(Lead.kind=='supplier',Lead.verification=='Verified')).all()
    ranked=[]; bqty=normalize_quantity(buyer.quantity)
    for s in suppliers:
        score=0; reasons=[]
        if (s.category or "").lower()==(buyer.category or "").lower(): score+=30; reasons.append('same category +30')
        if (s.product or "").lower()==(buyer.product or "").lower(): score+=30; reasons.append('same product +30')
        if buyer.state.lower()==s.state.lower(): score+=10; reasons.append('same state +10')
        # City bonus is intentionally an alternative to the state bonus, not additive.
        elif (buyer.city or "").lower()==(s.city or "").lower(): score+=15; reasons.append('same city +15')
        sqty=normalize_quantity(s.capacity)
        if bqty and sqty:
            if sqty>=bqty: score+=20; reasons.append('capacity covers requested quantity +20')
            else: reasons.append('capacity below requested quantity +0')
        elif s.capacity and buyer.quantity: score+=5; reasons.append('capacity stated; units need manual review +5')
        if s.moq: score+=5; reasons.append('MOQ stated +5')
        if s.indicative_price: score+=5; reasons.append('indicative price available +5')
        if score: ranked.append({'supplier':s,'score':score,'reasons':reasons})
    return sorted(ranked,key=lambda x:x['score'],reverse=True)[:10]
