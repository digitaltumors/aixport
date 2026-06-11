# AIxPORT Docker Smoke Checks

Build from the repository root:

```bash
make -C .dnanexus docker
```

Check the command entrypoint:

```bash
docker run --rm --platform linux/amd64 digitaltumors/aixport:0.1.0 --help
docker run --rm --platform linux/amd64 digitaltumors/aixport:0.1.0 vcf2inputs --help
```

Run a mounted `vcf2inputs` conversion:

```bash
docker run --rm --platform linux/amd64 \
  -v "$PWD:/work" \
  digitaltumors/aixport:0.1.0 \
  vcf2inputs /work/out_rocrate \
  --vcf /work/tests/fixtures/calls.vcf \
  --gene2ind /work/tests/fixtures/gene2ind.txt \
  --output-profile aixport
```
