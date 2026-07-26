import fakeredis

redis_client = fakeredis.FakeRedis(
    decode_responses=True
)