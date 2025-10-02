export function loadAsset(url: string): Promise<HTMLImageElement | HTMLAudioElement> {
    return new Promise((resolve, reject) => {
        const extension = url.split('.').pop();
        let asset;

        if (extension === 'png' || extension === 'jpg' || extension === 'jpeg') {
            asset = new Image();
            asset.src = url;
            asset.onload = () => resolve(asset);
            asset.onerror = () => reject(new Error(`Failed to load image: ${url}`));
        } else if (extension === 'mp3' || extension === 'wav') {
            asset = new Audio(url);
            asset.onloadeddata = () => resolve(asset);
            asset.onerror = () => reject(new Error(`Failed to load audio: ${url}`));
        } else {
            reject(new Error(`Unsupported asset type: ${url}`));
        }
    });
}

export const GLOBAL_CONSTANTS = {
    SCREEN_WIDTH: 800,
    SCREEN_HEIGHT: 600,
    FRAME_RATE: 60,
};