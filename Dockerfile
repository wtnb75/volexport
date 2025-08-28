FROM python:3-alpine AS build
COPY ./ /app
RUN --mount=type=cache,target=/root/.cache cd /app && pip install build && python -m build -w
RUN cd /app/dist && pip wheel -r ../requirements.txt

FROM python:3-alpine
RUN apk add --no-cache targetcli scsi-tgt scsi-tgt-scripts lvm2 lvm2-extra tini
RUN apk add --no-cache e2fsprogs exfatprogs btrfs-progs dosfstools xfsprogs nilfs-utils
ENV PYTHONDONTWRITEBYTECODE=1
COPY --from=build /app/dist/*.whl /dist/
ADD --chmod=755 entrypoint.sh /
RUN --mount=type=cache,target=/root/.cache pip install --no-compile /dist/*.whl
ENTRYPOINT ["tini", "--"]
EXPOSE 3260
EXPOSE 8080
CMD ["/entrypoint.sh"]
