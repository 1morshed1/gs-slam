# ORB-SLAM3 container (Phase 0)

## Build (office rig)

```bash
COMMIT=$(curl -sL https://api.github.com/repos/UZ-SLAMLab/ORB_SLAM3/commits/master \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['sha'])")
printf 'repo: https://github.com/UZ-SLAMLab/ORB_SLAM3\ncommit: %s\n' "$COMMIT" \
  > containers/orb_slam3/commit.lock

# Load into local docker (buildx docker-container driver needs --output type=docker)
docker buildx build \
  -f containers/orb_slam3/Dockerfile.x86 \
  --build-arg ORB_SLAM3_COMMIT="$COMMIT" \
  --output type=docker,name=harness/orb_slam3:x86 \
  -t harness/orb_slam3:x86 \
  containers/orb_slam3
```

## Run notes (shared office box)

Bind mounts (`docker run -v`) are **blocked by OPA** on this host. The harness adapter
falls back to `docker run -d` + `docker cp` + `docker exec` + `docker cp`.

Manual equivalent:

```bash
docker run -d --name orb_tmp --entrypoint sleep harness/orb_slam3:x86 3600
docker cp datasets/tum/rgbd_dataset_freiburg1_desk/. orb_tmp:/data/
docker exec orb_tmp bash -lc '/opt/entrypoint.sh --data /data --out /out'
docker cp orb_tmp:/out/. runs/manual_orb/
docker rm -f orb_tmp
```

## P0 gate (achieved 2026-09-23)

- Commit: `4452a3c4ab75b1cde34e5505a36ec3f9edcdc4c4`
- Sequence: TUM `rgbd_dataset_freiburg1_desk` (RGB-D, TUM1.yaml)
- **ATE-RMSE ≈ 0.0169 m** (1.69 cm) via evo, Sim(3)/SE(3) translation align — in family of published ORB-SLAM3 RGB-D fr1/desk numbers.
