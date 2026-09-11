"""Shared permission check used by both accounts/ (trainer/client pages)
and training/ (plan editing) -- kept here, rather than duplicated in each
app, since it's the single definition of "who may manage a given
Trainer's clients and plans."."""


def can_manage_trainer(user, trainer):
    """True if `user` is this Trainer themselves, or the Owner of the Gym
    this Trainer belongs to. This is the one rule behind "Only Owners and
    Trainers have write access" -- every plan/workout/phase/exercise edit
    boundary, and every trainer/client management page, is built on it."""
    return trainer.user_id == user.id or trainer.gym.owner_id == user.id
