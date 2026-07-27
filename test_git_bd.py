#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
================================================================================
 test_git_bd.py  --  Pruebas de la sincronizacion de la BD con GitHub (v3.1.0)
================================================================================
NO necesita internet ni un repositorio real:

  * Backend git  -> se crea un repositorio *bare* local que hace de "GitHub" y
                    dos clones que hacen de PC1 y PC2. Todo lo que se prueba
                    (pull, push, merge, conflictos) es git de verdad.
  * Backend REST -> se sustituye la capa HTTP por un "GitHub" en memoria que
                    implementa los mismos endpoints (refs/commits/trees/blobs),
                    incluido el rechazo del ``ref`` cuando otra PC subio antes.

Cubre lo pedido en la especificacion:
  1. Sincronizacion normal:  PC1 carga una ficha  ->  PC2 la ve.
  2. Conflicto simple:       las dos PCs modifican indice.json  ->  se resuelve
                             solo y NO se pierde ninguna ficha.
  3. Colision de PDFs:       las dos PCs suben un PDF distinto con el mismo
                             nombre  ->  se conservan los dos.
  4. Sin conexion:           la app sigue trabajando y sube al reconectar.
  5. Push rechazado:         se reintenta tras fusionar.
  6. Rama/repo inaccesible:  se detecta y se avisa (no se corrompe nada).

Ejecutar:
    python -m unittest test_git_bd -v
================================================================================
"""

import os
import json
import base64
import shutil
import hashlib
import tempfile
import subprocess
import unittest
from pathlib import Path
from datetime import datetime, timedelta

import git_bd
import bd_manager as bd

PDF_A = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\nA"
PDF_B = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\nBBBB"


def _git(args, cwd):
    """git para el andamiaje de las pruebas (con identidad fija)."""
    cmd = ["git", "-c", "user.name=Prueba", "-c", "user.email=prueba@local",
           "-c", "commit.gpgsign=false", "-C", str(cwd)] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(f"git {args}: {r.stderr}")
    return r.stdout


# ==========================================================================
# UNIT: fusion del indice (independiente del transporte)
# ==========================================================================
class TestMergeIndices(unittest.TestCase):
    """El corazon de 'nunca se pierden datos'."""

    def _ficha(self, fid, nombre="Tubo", cuando=None, estado="activo"):
        return {"id": fid, "nombre_material": nombre, "marca": "M",
                "categoria": "ESTR", "ruta_pdf": f"ESTR/{fid}.pdf",
                "hash_archivo": fid, "estado": estado,
                "fecha_modificacion": (cuando or datetime.now()).replace(
                    microsecond=0).isoformat()}

    def test_union_no_pierde_ninguna_ficha(self):
        base = {"fichas": [self._ficha("comun")]}
        nuestro = {"fichas": [self._ficha("comun"), self._ficha("local")]}
        suyo = {"fichas": [self._ficha("comun"), self._ficha("remota")]}
        fus, res = git_bd.merge_indices(base, nuestro, suyo)
        ids = {f["id"] for f in fus["fichas"]}
        self.assertEqual(ids, {"comun", "local", "remota"})
        self.assertEqual(res["remotas_nuevas"], 1)
        self.assertEqual(res["locales_conservadas"], 1)

    def test_mismo_id_gana_el_mas_reciente(self):
        viejo = datetime.now() - timedelta(hours=2)
        nuestro = {"fichas": [self._ficha("x", nombre="LOCAL-NUEVO")]}
        suyo = {"fichas": [self._ficha("x", nombre="REMOTO-VIEJO", cuando=viejo)]}
        fus, res = git_bd.merge_indices(None, nuestro, suyo)
        self.assertEqual(len(fus["fichas"]), 1)
        self.assertEqual(fus["fichas"][0]["nombre_material"], "LOCAL-NUEVO")
        self.assertEqual(res["gano_local"], 1)

        # Y al reves: si el remoto es mas nuevo, gana el remoto.
        nuestro = {"fichas": [self._ficha("x", nombre="LOCAL-VIEJO", cuando=viejo)]}
        suyo = {"fichas": [self._ficha("x", nombre="REMOTO-NUEVO")]}
        fus, res = git_bd.merge_indices(None, nuestro, suyo)
        self.assertEqual(fus["fichas"][0]["nombre_material"], "REMOTO-NUEVO")
        self.assertEqual(res["gano_remoto"], 1)

    def test_soft_delete_reciente_se_respeta(self):
        viejo = datetime.now() - timedelta(days=1)
        nuestro = {"fichas": [self._ficha("x", cuando=viejo, estado="activo")]}
        suyo = {"fichas": [self._ficha("x", estado="inactivo")]}
        fus, _ = git_bd.merge_indices(None, nuestro, suyo)
        self.assertEqual(fus["fichas"][0]["estado"], "inactivo")

    def test_ficha_local_ausente_en_remoto_se_conserva(self):
        # Nunca se interpreta una ausencia como un borrado.
        base = {"fichas": [self._ficha("a"), self._ficha("b")]}
        nuestro = {"fichas": [self._ficha("a"), self._ficha("b")]}
        suyo = {"fichas": [self._ficha("a")]}
        fus, _ = git_bd.merge_indices(base, nuestro, suyo)
        self.assertEqual({f["id"] for f in fus["fichas"]}, {"a", "b"})

    def test_renombre_reapunta_ruta_pdf(self):
        f = self._ficha("x")
        f["hash_archivo"] = "abc123"
        f["ruta_pdf"] = "ESTR/tubo.pdf"
        fus, _ = git_bd.merge_indices(None, {"fichas": [f]}, {"fichas": []},
                                      renombres=[{"ruta": "ESTR/tubo.pdf",
                                                  "hash": "abc123",
                                                  "nueva": "ESTR/tubo-2.pdf"}])
        self.assertEqual(fus["fichas"][0]["ruta_pdf"], "ESTR/tubo-2.pdf")

    def test_indice_corrupto_no_rompe_la_fusion(self):
        fus, _ = git_bd.merge_indices(None, None, {"fichas": [self._ficha("a")]})
        self.assertEqual(len(fus["fichas"]), 1)


class TestValidarIndice(unittest.TestCase):

    def test_indice_valido(self):
        ok, errs = bd.validar_indice({
            "version": "3.1.0",
            "fichas": [{"id": "1", "nombre_material": "T", "marca": "M",
                        "categoria": "ESTR", "ruta_pdf": "ESTR/t.pdf"}]})
        self.assertTrue(ok, errs)

    def test_detecta_ids_duplicados_y_campos_faltantes(self):
        ok, errs = bd.validar_indice({
            "version": "3.1.0",
            "fichas": [{"id": "1", "nombre_material": "T", "marca": "M",
                        "categoria": "ESTR", "ruta_pdf": "a.pdf"},
                       {"id": "1", "nombre_material": "", "marca": "M",
                        "categoria": "ESTR", "ruta_pdf": ""}]})
        self.assertFalse(ok)
        texto = " ".join(errs)
        self.assertIn("duplicado", texto)
        self.assertIn("nombre_material", texto)
        self.assertIn("ruta_pdf", texto)

    def test_rechaza_version_futura(self):
        ok, errs = bd.validar_indice({"version": "4.0.0", "fichas": []})
        self.assertFalse(ok)
        self.assertIn("Version", " ".join(errs))


# ==========================================================================
# BACKEND GIT: dos PCs contra un "GitHub" local
# ==========================================================================
@unittest.skipUnless(git_bd.git_disponible(), "git no esta instalado")
class TestDosPCs(unittest.TestCase):
    """Cada PC es un clon independiente del mismo repositorio bare."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.remoto = self.tmp / "remoto.git"
        self.remoto.mkdir()
        try:
            _git(["init", "--bare", "-b", "main"], cwd=self.remoto)
        except AssertionError:
            _git(["init", "--bare"], cwd=self.remoto)
            _git(["symbolic-ref", "HEAD", "refs/heads/main"], cwd=self.remoto)
        self._sembrar()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _sembrar(self):
        """Primer commit: BD vacia (como quedaria el repo real tras publicar)."""
        semilla = self.tmp / "semilla"
        _git(["clone", str(self.remoto), str(semilla)], cwd=self.tmp)
        bdir = semilla / "BD_Submittals"
        for sub in ("ARQ", "ESTR", "MEC", "ELEC", "Proyectos"):
            (bdir / sub).mkdir(parents=True, exist_ok=True)
            (bdir / sub / ".gitkeep").write_text("")
        (bdir / "indice.json").write_text(json.dumps(
            {"version": "3.1.0", "ultima_actualizacion": bd.ahora_iso(),
             "fichas": []}, ensure_ascii=False, indent=2), encoding="utf-8")
        _git(["add", "-A"], cwd=semilla)
        _git(["commit", "-m", "BD inicial"], cwd=semilla)
        _git(["push", "origin", "HEAD:refs/heads/main"], cwd=semilla)
        shutil.rmtree(semilla, ignore_errors=True)

    def _pc(self, nombre):
        """Construye un BDManager que sincroniza con el 'GitHub' local."""
        base = self.tmp / nombre
        sync = git_bd.GitSync(base_dir=base, repo_slug="local/prueba", rama="main",
                              subdir="BD_Submittals", usuario=nombre,
                              email=f"{nombre}@local", modo=git_bd.MODO_GIT,
                              cache_dir=base / "cache", url=str(self.remoto))
        m = bd.BDManager(cache_dir=base / "cache", config_dir=base / "cfg", sync=sync)
        m.sincronizar()
        m.inicializar_bd()
        return m

    def _pdf(self, nombre, datos=PDF_A):
        p = self.tmp / nombre
        p.write_bytes(datos)
        return str(p)

    def _agregar(self, m, nombre="Tubo 150", marca="MultiGroup", cat="ESTR",
                 datos=PDF_A):
        return m.agregar_ficha(self._pdf(f"src-{nombre}-{marca}.pdf", datos), {
            "nombre_material": nombre, "marca": marca, "categoria": cat,
            "dimensiones": "150x100", "normativa": "ASTM A500M",
            "descripcion_corta": "Tubo de acero"})

    # ------------------------------------------------------------------ 1
    def test_clon_inicial_deja_la_bd_lista(self):
        pc1 = self._pc("pc1")
        self.assertEqual(pc1.git_status()["backend"], "git")
        self.assertTrue(pc1.bd_root.is_dir())
        self.assertTrue(pc1.indice_path.exists())
        self.assertEqual(len(pc1.listar_fichas()), 0)

    def test_sincronizacion_normal_pc1_carga_pc2_ve(self):
        pc1 = self._pc("pc1")
        f = self._agregar(pc1, "Tubo 150", "MultiGroup")
        r = pc1.git_push("agregar tubo")
        self.assertTrue(r["subido"], r)
        self.assertFalse(pc1.hay_cambios_sin_subir())

        pc2 = self._pc("pc2")
        fichas = pc2.listar_fichas()
        self.assertEqual(len(fichas), 1)
        self.assertEqual(fichas[0]["id"], f["id"])
        # El PDF tambien llego (sparse checkout de la carpeta completa).
        self.assertTrue((pc2.bd_root / fichas[0]["ruta_pdf"]).exists())
        # ...y se puede usar para generar entregables.
        self.assertTrue(Path(pc2.ruta_local_ficha(fichas[0])).exists())

    # ------------------------------------------------------------------ 2
    def test_conflicto_indice_conserva_las_dos_fichas(self):
        """El caso critico: las dos PCs cargan una ficha a la vez."""
        pc1 = self._pc("pc1")
        pc2 = self._pc("pc2")            # las dos parten del mismo commit

        f1 = self._agregar(pc1, "Tubo 150", "MultiGroup")
        f2 = self._agregar(pc2, "Cemento", "Holcim")

        self.assertTrue(pc1.git_push("ficha de pc1")["subido"])

        # pc2 empuja sobre un remoto que ya se movio -> conflicto en indice.json
        r2 = pc2.git_push("ficha de pc2")
        self.assertTrue(r2["subido"], r2)
        self.assertGreaterEqual(r2["reintentos"], 1)

        # Las dos fichas sobreviven en las dos PCs.
        ids2 = {x["id"] for x in pc2.listar_fichas()}
        self.assertEqual(ids2, {f1["id"], f2["id"]})
        pc1.sincronizar()
        ids1 = {x["id"] for x in pc1.listar_fichas()}
        self.assertEqual(ids1, {f1["id"], f2["id"]})
        # Y el indice sigue siendo valido.
        ok, errs = bd.validar_indice(pc1.cargar_indice())
        self.assertTrue(ok, errs)
        # Los dos PDFs estan presentes.
        for f in pc1.listar_fichas():
            self.assertTrue((pc1.bd_root / f["ruta_pdf"]).exists(), f["ruta_pdf"])

    # ------------------------------------------------------------------ 3
    def test_colision_de_nombre_de_pdf_conserva_los_dos(self):
        """Las dos PCs cargan un material con el mismo nombre pero PDFs
        distintos: el nombre de archivo choca y hay que conservar ambos."""
        pc1 = self._pc("pc1")
        pc2 = self._pc("pc2")

        f1 = self._agregar(pc1, "Tubo 150", "MultiGroup", datos=PDF_A)
        f2 = self._agregar(pc2, "Tubo 150", "MultiGroup", datos=PDF_B)
        self.assertEqual(f1["ruta_pdf"], f2["ruta_pdf"])   # mismo slug

        self.assertTrue(pc1.git_push("pdf de pc1")["subido"])
        r2 = pc2.git_push("pdf de pc2")
        self.assertTrue(r2["subido"], r2)

        fichas = pc2.listar_fichas()
        self.assertEqual(len(fichas), 2)
        rutas = {f["ruta_pdf"] for f in fichas}
        self.assertEqual(len(rutas), 2, f"las rutas deben diferenciarse: {rutas}")
        # Cada archivo existe y su contenido corresponde al hash de su ficha.
        for f in fichas:
            p = pc2.bd_root / f["ruta_pdf"]
            self.assertTrue(p.exists(), p)
            self.assertEqual(bd.sha256_file(p), f["hash_archivo"])
        # Los dos contenidos originales sobreviven.
        contenidos = {(pc2.bd_root / f["ruta_pdf"]).read_bytes() for f in fichas}
        self.assertEqual(contenidos, {PDF_A, PDF_B})

    # ------------------------------------------------------------------ 4
    def test_edicion_simultanea_de_la_misma_ficha(self):
        pc1 = self._pc("pc1")
        f = self._agregar(pc1, "Tubo 150", "MultiGroup")
        pc1.git_push("alta")
        pc2 = self._pc("pc2")

        # pc2 edita primero (mas antiguo), pc1 despues (mas reciente).
        pc2.actualizar_ficha(f["id"], {"marca": "Metalco"})
        data = pc2.cargar_indice()
        for x in data["fichas"]:
            x["fecha_modificacion"] = (datetime.now() - timedelta(hours=1)
                                       ).replace(microsecond=0).isoformat()
        pc2._guardar_indice(data)

        pc1.actualizar_ficha(f["id"], {"marca": "MarcaGanadora"})
        self.assertTrue(pc1.git_push("edicion pc1")["subido"])
        r2 = pc2.git_push("edicion pc2")
        self.assertTrue(r2["subido"], r2)

        # Gana la edicion mas reciente, y sigue habiendo una sola ficha.
        fichas = pc2.listar_fichas()
        self.assertEqual(len(fichas), 1)
        self.assertEqual(fichas[0]["marca"], "MarcaGanadora")

    # ------------------------------------------------------------------ 5
    def test_metadatos_de_proyecto_viajan_entre_pcs(self):
        pc1 = self._pc("pc1")
        f = self._agregar(pc1, "Tubo 150", "MultiGroup")
        proyecto = {"nombre_proyecto": "Obra Muni",
                    "datos_procedimiento": {"numero_procedimiento": "2026LA-1",
                                            "institucion": "Muni", "detalle": "obra",
                                            "plazo": "6m", "monto": "1000"},
                    "materiales_seleccionados": [
                        {"consecutivo": "ESTR01", "id_ficha_bd": f["id"],
                         "categoria": "ESTR", "nombre_material": "Tubo 150",
                         "marca": "MultiGroup"}]}
        pc1.guardar_submittal(proyecto)
        self.assertTrue(pc1.git_push("submittal Obra Muni")["subido"])

        pc2 = self._pc("pc2")
        proyectos = pc2.listar_proyectos()
        self.assertEqual(len(proyectos), 1)
        self.assertEqual(proyectos[0]["nombre_proyecto"], "Obra Muni")
        self.assertEqual(proyectos[0]["materiales"], 1)

    # ------------------------------------------------------------------ 6
    def test_sin_conexion_trabaja_local_y_sube_al_reconectar(self):
        pc1 = self._pc("pc1")
        caido = self.tmp / "remoto_caido.git"

        # "Cortar la conexion": el remoto deja de existir.
        self.remoto.rename(caido)
        f = self._agregar(pc1, "Tubo Offline", "MultiGroup")
        r = pc1.git_push("ficha sin conexion")
        self.assertFalse(r["subido"])
        self.assertTrue(r.get("offline") or r.get("error"), r)
        # El trabajo NO se pierde: la ficha esta en la BD local.
        self.assertEqual(len(pc1.listar_fichas()), 1)
        self.assertTrue((pc1.bd_root / f["ruta_pdf"]).exists())
        # Y la app sabe que quedo algo pendiente.
        self.assertTrue(pc1.hay_cambios_sin_subir())
        est = pc1.git_status()
        self.assertTrue(est["offline"] or est["pendientes"])

        # Reconectar -> se sube solo.
        caido.rename(self.remoto)
        r2 = pc1.git_push("subir pendientes")
        self.assertTrue(r2["subido"], r2)
        pc2 = self._pc("pc2")
        self.assertEqual([x["id"] for x in pc2.listar_fichas()], [f["id"]])

    def test_indice_corrupto_cae_al_cache(self):
        pc1 = self._pc("pc1")
        self._agregar(pc1, "Tubo 150", "MultiGroup")
        self.assertTrue(pc1.cache_indice.exists())
        pc1.indice_path.write_text("{ esto no es json", encoding="utf-8")
        original = bd.ESPERA_REINTENTO_SEG
        bd.ESPERA_REINTENTO_SEG = 0
        try:
            data = pc1.cargar_indice()
        finally:
            bd.ESPERA_REINTENTO_SEG = original
        self.assertTrue(pc1.usando_cache)
        self.assertEqual(len(data["fichas"]), 1)

    def test_repo_inexistente_avisa_sin_romper(self):
        base = self.tmp / "pcx"
        sync = git_bd.GitSync(base_dir=base, rama="main", modo=git_bd.MODO_GIT,
                              cache_dir=base / "cache",
                              url=str(self.tmp / "no-existe.git"))
        r = sync.pull()
        self.assertFalse(r.get("recibidos"))
        self.assertTrue(r.get("offline") or r.get("error"), r)
        # La interfaz debe REPORTAR el problema, no fingir que todo esta bien.
        texto = sync.texto_estado()
        self.assertTrue(texto.startswith(("📡", "⚠️")), texto)
        self.assertTrue(sync.ultimo_error)

    def test_el_token_nunca_aparece_en_los_mensajes(self):
        t = git_bd.GitTransporte(self.tmp / "pct", token="ghp_SECRETO123",
                                 rama="main")
        self.assertNotIn("ghp_SECRETO123",
                         t._ocultar("fallo https://x-access-token:ghp_SECRETO123@github.com"))
        self.assertIn("***",
                      t._ocultar("fallo https://x-access-token:ghp_SECRETO123@github.com"))

    def test_push_sin_token_pide_configurarlo(self):
        """Contra GitHub real (no un remoto local) el push exige token."""
        t = git_bd.GitTransporte(self.tmp / "pcz", repo_slug="adrianix360/x",
                                 rama="main", token="")
        t.inicializar = lambda: False
        t._commit_local = lambda mensaje: True
        t._tiene_commits = lambda: True
        with self.assertRaises(git_bd.AutenticacionError):
            t.push("intento")


# ==========================================================================
# BACKEND REST: "GitHub" en memoria (PCs sin git instalado)
# ==========================================================================
class FakeGitHub:
    """Implementa en memoria los endpoints que usa ``RestTransporte``."""

    def __init__(self):
        self.blobs = {}      # sha -> bytes
        self.trees = {}      # sha -> {path: blob_sha}
        self.commits = {}    # sha -> {"tree": sha, "parents": [...]}
        self.ref = ""
        self.intromision = None   # callable: simula que otra PC subio antes
        self.peticiones = 0

    # -- helpers ----------------------------------------------------------
    def _sha(self, datos):
        return hashlib.sha256(datos).hexdigest()

    def sembrar(self, archivos):
        tree = {}
        for ruta, datos in archivos.items():
            s = self._sha(datos)
            self.blobs[s] = datos
            tree[ruta] = s
        tsha = self._sha(json.dumps(sorted(tree.items())).encode())
        self.trees[tsha] = tree
        csha = self._sha(b"commit" + tsha.encode())
        self.commits[csha] = {"tree": tsha, "parents": []}
        self.ref = csha

    def archivos(self):
        tree = self.trees[self.commits[self.ref]["tree"]]
        return {ruta: self.blobs[s] for ruta, s in tree.items()}

    # -- capa HTTP simulada ----------------------------------------------
    def req(self, metodo, ruta, cuerpo=None, raw=False):
        self.peticiones += 1
        ruta = ruta.split("?")[0]
        partes = ruta.strip("/").split("/")
        cola = partes[3:]          # repos/<owner>/<repo>/git/...

        if metodo == "GET" and cola[:2] == ["git", "ref"]:
            if not self.ref:
                raise git_bd.RepoNoEncontradoError("rama inexistente")
            return {"object": {"sha": self.ref}}, 200
        if metodo == "GET" and cola[:2] == ["git", "commits"]:
            c = self.commits[cola[2]]
            return {"sha": cola[2], "tree": {"sha": c["tree"]}}, 200
        if metodo == "GET" and cola[:2] == ["git", "trees"]:
            tree = self.trees[cola[2]]
            return {"tree": [{"path": p, "type": "blob", "sha": s}
                             for p, s in sorted(tree.items())]}, 200
        if metodo == "GET" and cola[:2] == ["git", "blobs"]:
            return self.blobs[cola[2]], 200
        if metodo == "POST" and cola[:2] == ["git", "blobs"]:
            datos = base64.b64decode(cuerpo["content"])
            s = self._sha(datos)
            self.blobs[s] = datos
            return {"sha": s}, 201
        if metodo == "POST" and cola[:2] == ["git", "trees"]:
            nuevo = dict(self.trees.get(cuerpo.get("base_tree", ""), {}))
            for e in cuerpo["tree"]:
                nuevo[e["path"]] = e["sha"]
            tsha = self._sha(json.dumps(sorted(nuevo.items())).encode())
            self.trees[tsha] = nuevo
            return {"sha": tsha}, 201
        if metodo == "POST" and cola[:2] == ["git", "commits"]:
            csha = self._sha(json.dumps(
                [cuerpo["tree"], cuerpo.get("parents", []),
                 cuerpo.get("message", ""), str(self.peticiones)]).encode())
            self.commits[csha] = {"tree": cuerpo["tree"],
                                  "parents": cuerpo.get("parents", [])}
            return {"sha": csha}, 201
        if metodo == "PATCH" and cola[:2] == ["git", "refs"]:
            if self.intromision:
                f, self.intromision = self.intromision, None
                f(self)
            nuevo = cuerpo["sha"]
            padres = self.commits[nuevo]["parents"]
            if padres and padres[0] != self.ref:
                return {"_conflicto": True, "_detalle": "not a fast forward"}, 422
            self.ref = nuevo
            return {"object": {"sha": nuevo}}, 200
        raise AssertionError(f"endpoint no simulado: {metodo} {ruta}")


class RestPrueba(git_bd.RestTransporte):
    """RestTransporte con la capa HTTP sustituida por ``FakeGitHub``."""

    def __init__(self, *a, servidor=None, **kw):
        super().__init__(*a, **kw)
        self.servidor = servidor

    def _req(self, metodo, ruta, cuerpo=None, raw=False):
        return self.servidor.req(metodo, ruta, cuerpo, raw)


class TestBackendRest(unittest.TestCase):
    """Mismo comportamiento sin git instalado."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.gh = FakeGitHub()
        self.gh.sembrar({"BD_Submittals/indice.json": json.dumps(
            {"version": "3.1.0", "fichas": []}).encode("utf-8")})

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _pc(self, nombre):
        base = self.tmp / nombre
        t = RestPrueba(base / "bd_local", repo_slug="local/prueba", rama="main",
                       subdir="BD_Submittals", token="token-falso", usuario=nombre,
                       estado_path=base / "cache" / "rest_state.json",
                       servidor=self.gh)
        sync = git_bd.GitSync(base_dir=base, modo=git_bd.MODO_REST,
                              cache_dir=base / "cache")
        sync.t = t
        m = bd.BDManager(cache_dir=base / "cache", config_dir=base / "cfg", sync=sync)
        m.sincronizar()
        m.inicializar_bd()
        return m

    def _agregar(self, m, nombre, marca, datos=PDF_A):
        p = self.tmp / f"src-{nombre}-{marca}.pdf"
        p.write_bytes(datos)
        return m.agregar_ficha(str(p), {"nombre_material": nombre, "marca": marca,
                                        "categoria": "ESTR",
                                        "descripcion_corta": "x"})

    def test_backend_rest_sin_git(self):
        pc1 = self._pc("pc1")
        self.assertEqual(pc1.git_status()["backend"], "rest")
        self.assertTrue(pc1.sync.necesita_descarga_diferida())

    def test_pc1_sube_pc2_descarga_pdf_bajo_demanda(self):
        pc1 = self._pc("pc1")
        f = self._agregar(pc1, "Tubo 150", "MultiGroup")
        r = pc1.git_push("alta de ficha")
        self.assertTrue(r["subido"], r)
        self.assertIn(f"BD_Submittals/{f['ruta_pdf']}", self.gh.archivos())

        pc2 = self._pc("pc2")
        fichas = pc2.listar_fichas()
        self.assertEqual(len(fichas), 1)
        # El PDF no se descarga hasta que se necesita...
        self.assertFalse((pc2.bd_root / fichas[0]["ruta_pdf"]).exists())
        # ...y al pedirlo, llega.
        local = pc2.ruta_local_ficha(fichas[0])
        self.assertTrue(Path(local).exists())
        self.assertEqual(Path(local).read_bytes(), PDF_A)

    def test_conflicto_rest_conserva_las_dos_fichas(self):
        pc1 = self._pc("pc1")
        pc2 = self._pc("pc2")
        f1 = self._agregar(pc1, "Tubo 150", "MultiGroup")
        f2 = self._agregar(pc2, "Cemento", "Holcim")
        self.assertTrue(pc1.git_push("pc1")["subido"])
        self.assertTrue(pc2.git_push("pc2")["subido"])

        remoto = json.loads(self.gh.archivos()["BD_Submittals/indice.json"])
        self.assertEqual({x["id"] for x in remoto["fichas"]}, {f1["id"], f2["id"]})

    def test_push_rechazado_reintenta_y_fusiona(self):
        """Otra PC mueve el ref justo entre el commit y el PATCH."""
        pc1 = self._pc("pc1")
        pc2 = self._pc("pc2")
        f2 = self._agregar(pc2, "Cemento", "Holcim")
        f1 = self._agregar(pc1, "Tubo 150", "MultiGroup")

        def se_adelanta(gh):
            pc2.git_push("pc2 se adelanta")

        self.gh.intromision = se_adelanta
        r = pc1.git_push("pc1 pierde la carrera")
        self.assertTrue(r["subido"], r)
        self.assertGreaterEqual(r["reintentos"], 1)
        remoto = json.loads(self.gh.archivos()["BD_Submittals/indice.json"])
        self.assertEqual({x["id"] for x in remoto["fichas"]}, {f1["id"], f2["id"]})

    def test_colision_de_pdf_en_rest(self):
        pc1 = self._pc("pc1")
        pc2 = self._pc("pc2")
        self._agregar(pc1, "Tubo 150", "MultiGroup", datos=PDF_A)
        self._agregar(pc2, "Tubo 150", "MultiGroup", datos=PDF_B)
        self.assertTrue(pc1.git_push("pc1")["subido"])
        self.assertTrue(pc2.git_push("pc2")["subido"])

        archivos = self.gh.archivos()
        pdfs = {r: d for r, d in archivos.items() if r.endswith(".pdf")}
        self.assertEqual(len(pdfs), 2, pdfs.keys())
        self.assertEqual(set(pdfs.values()), {PDF_A, PDF_B})
        indice = json.loads(archivos["BD_Submittals/indice.json"])
        rutas = {f["ruta_pdf"] for f in indice["fichas"]}
        self.assertEqual(len(rutas), 2, rutas)

    def test_sin_token_no_sube(self):
        pc1 = self._pc("pc1")
        pc1.sync.set_token("")
        self._agregar(pc1, "Tubo", "M")
        r = pc1.git_push("sin token")
        self.assertFalse(r["subido"])
        self.assertTrue(r.get("auth"))


class TestTextoEstado(unittest.TestCase):

    def test_hace_minutos(self):
        hace5 = (datetime.now() - timedelta(minutes=5)).replace(microsecond=0).isoformat()
        self.assertEqual(git_bd._hace(hace5), "hace 5 min")
        self.assertEqual(git_bd._hace(""), "—")

    def test_texto_offline(self):
        s = git_bd.GitSync(Path(tempfile.mkdtemp()), modo=git_bd.MODO_REST)
        s.offline = True
        self.assertIn("Sin conexión", s.texto_estado())


if __name__ == "__main__":
    unittest.main(verbosity=2)
