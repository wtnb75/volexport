FROM python:3-alpine AS build
COPY ./ /app
RUN --mount=type=cache,target=/root/.cache cd /app && pip install build && python -m build -w
RUN cd /app/dist && pip wheel -r ../requirements.txt

FROM python:3-alpine
RUN apk add --no-cache targetcli scsi-tgt scsi-tgt-scripts lvm2 lvm2-extra tini
ENV PYTHONDONTWRITEBYTECODE=1
COPY --from=build /app/dist/*.whl /dist/
ADD --chmod=755 entrypoint.sh /
RUN --mount=type=cache,target=/root/.cache pip install --no-compile /dist/*.whl
ENTRYPOINT ["tini", "--"]
CMD ["/entrypoint.sh"]
