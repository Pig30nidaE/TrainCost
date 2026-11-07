"""Pure CUDA preflight contracts; these tests do not execute CUDA."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from worker import validate_cuda_runtime, validate_cuda_wheel

URL = ("https://download.pytorch.org/whl/cu130/"
       "torch-2.14.1%2Bcu130-cp312-cp312-manylinux_2_28_x86_64.whl"
       "#sha256=5359b255ac68c0cabb8293952b38e00f0d1a570815cd87f19b61af702c071410")


class CudaEnvironmentTests(unittest.TestCase):
    def test_reviewed_wheel_and_host_driver_contract(self):
        validate_cuda_wheel(URL, "2.14.1+cu130")
        for driver in ("580.88", "580.65.06", "590.10"):
            validate_cuda_runtime(driver, "13.0")

    def test_unreviewed_host_build_platform_or_hash_fails(self):
        for url in (URL.replace("https:", "http:"), URL.replace("download.pytorch.org", "example.invalid"),
                    URL.replace("cu130", "cu126"), URL.replace("cp312", "cp311"),
                    URL.replace("x86_64", "aarch64"), URL.split("#")[0], URL + "bad",
                    URL.replace("#", "?alternate=1#")):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_cuda_wheel(url, "2.14.1+cu130")
        with self.assertRaises(ValueError):
            validate_cuda_wheel(URL, "2.9.1+cu126")

    def test_old_or_unparseable_driver_and_wrong_runtime_fail(self):
        for driver, runtime in (("579.99", "13.0"), ("550.00", "13.0"), ("unknown", "13.0"),
                                ("580.88", "12.6"), ("580.88", None)):
            with self.subTest(driver=driver, runtime=runtime), self.assertRaises(ValueError):
                validate_cuda_runtime(driver, runtime)


if __name__ == "__main__":
    unittest.main()
