from functools import wraps


def property_cache_once_per_frame(f):
    """This decorator caches the return value for one game loop,
    then clears it if it is accessed in a different game loop.
    Only works on properties of the bot object, because it requires
    access to self.state.game_loop"""

    @wraps(f)
    def inner(self):
        property_cache = "_cache_" + f.__name__
        state_cache = "_frame_" + f.__name__
        cache_updated = getattr(self.bot, state_cache, -1) == self.bot.state.game_loop
        if not cache_updated:
            setattr(self.bot, property_cache, f(self))
            setattr(self.bot, state_cache, self.bot.state.game_loop)

        cache = getattr(self.bot, property_cache)
        should_copy = callable(getattr(cache, "copy", None))
        if should_copy:
            return cache.copy()
        return cache

    return property(inner)
