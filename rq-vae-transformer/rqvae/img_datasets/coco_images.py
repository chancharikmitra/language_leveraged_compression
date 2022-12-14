import os.path
from typing import Any, Callable, Optional, Tuple, List

from PIL import Image

from torchvision.datasets import VisionDataset

class CocoImages(VisionDataset):
    """ A dataset class that returns just the images of MS COCO """
    def __init__(
                self,
                root: str,
                annFile: str,
                transform: Optional[Callable] = None,
                target_transform: Optional[Callable] = None,
                transforms: Optional[Callable] = None,
                ) -> None:
        super().__init__(root, transforms, transform, target_transform)
        from pycocotools.coco import COCO

        self.coco = COCO(annFile)
        self.ids = list(sorted(self.coco.imgs.keys()))
    def _load_image(self, id: int) -> Image.Image:
        path = self.coco.loadImgs(id)[0]["file_name"]
        return Image.open(os.path.join(self.root, path)).convert("RGB")
    def _load_target(self, id: int) -> List[Any]:
        return self.coco.loadAnns(self.coco.getAnnIds(id))
    def __getitem__(self, index: int) -> Tuple[Any, Any]:
        id = self.ids[index]
        image = self._load_image(id)
        target = self._load_target(id)

        if self.transforms is not None:
            image, target = self.transforms(image, target)
        return image, 0
    def __len__(self) -> int:
        return len(self.ids)
