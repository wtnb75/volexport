FROM python:3-alpine AS build
COPY ./ /app
RUN --mount=type=cache,target=/root/.cache cd /app && pip install build && python -m build -w
RUN cd /app/dist && pip wheel -r ../requirements.txt

FROM python:3-alpine
RUN apk add --no-cache targetcli scsi-tgt lvm2 lvm2-extra
ENV PYTHONDONTWRITEBYTECODE=1
COPY --from=build /app/dist/*.whl /dist/
RUN --mount=type=cache,target=/root/.cache pip install --no-compile /dist/*.whl
