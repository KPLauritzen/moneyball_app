from app import db
from app.models import User, Rating, Match, UserMatch
from datetime import datetime

def create_user(shortname, nickname, password):
    user = User(
        shortname=shortname,
        nickname=nickname
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    init_ratings(user)
    return user

def init_ratings(user, timestamp=None):
    if timestamp is None:
        timestamp = datetime.now()
    r_elo = Rating(user=user, rating_type='elo', rating_value=1500, 
        timestamp=timestamp)
    r_ts_m = Rating(user=user, rating_type='trueskill_mu', 
        rating_value=25, timestamp=timestamp)
    r_ts_s = Rating(user=user, rating_type='trueskill_sigma', 
        rating_value=8.333, timestamp=timestamp)
    db.session.add_all([r_elo, r_ts_m, r_ts_s])
    db.session.commit()

def recalculate_ratings():
    users = User.query.all()
    timestamps = []
    for u in users:
        timestamps.append(Rating.query \
            .filter(Rating.user_id == u.id) \
            .filter(Rating.rating_type == 'elo') \
            .order_by(Rating.timestamp) \
            .first().timestamp )
    db.session.query(Rating).delete()
    db.session.commit()
    for u, t in zip(users, timestamps):
        init_ratings(u, t)

    matches = Match.query.order_by(Match.timestamp).all()
    for match in matches:
        update_match_ratings(match)

def delete_match(match):
    db.session.delete(match)
    db.session.commit()
    recalculate_ratings()

def update_match_ratings(match):
    elo_change = get_match_elo_change(match)
    for p in match.winning_players:
        r = Rating(user=p, match=match, rating_type='elo', 
        rating_value=p.get_current_elo() + elo_change,
        timestamp=match.timestamp)
        db.session.add(r)
    for p in match.losing_players:
        r = Rating(user=p, match=match, rating_type='elo',
        rating_value=p.get_current_elo() - elo_change,
        timestamp=match.timestamp)
        db.session.add(r)
    db.session.commit()

def get_match_elo_change(match):
    Qs = []
    for players in [match.winning_players, match.losing_players]:
        elos = [p.get_current_elo() for p in players]
        avg_elo = sum(elos) / len(elos)
        Q = 10 ** (avg_elo / 400)
        Qs.append(Q)
    Q_w, Q_l = Qs
    exp_win = Q_w / (Q_w + Q_l)
    change_w = match.importance * (1 - exp_win)
    return change_w


def make_new_match(winners, losers, w_score, l_score, importance):
    match = Match(
        winner_score=w_score, 
        loser_score=l_score,
        importance=importance)
    db.session.add(match)
    db.session.flush()

    for w in winners:
        user_match = UserMatch(
            user=w,
            match=match, 
            win=True)
        db.session.add(user_match)
    for l in losers:
        user_match = UserMatch(
            user=l,
            match=match, 
            win=False)
        db.session.add(user_match)
    db.session.flush()
    
    update_match_ratings(match)
    db.session.commit()
    return match