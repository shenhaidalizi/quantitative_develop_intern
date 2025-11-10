# up & down service:
up:
make up
docker-compose up -d

down:
make down

# recompose
docker-compose build

# fully recompose
docker-compose build --no-cache

# log:
docker logs stock-analyzer --tail 30

# build + restart
make build
make restart
