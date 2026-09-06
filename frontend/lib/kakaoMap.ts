// 여러 컴포넌트가 동시에 호출해도 스크립트 태그를 한 번만 삽입하도록 캐시한다.
let sdkPromise: Promise<any> | null = null;

export function loadKakaoMapsSdk(): Promise<any> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("loadKakaoMapsSdk can only run in the browser"));
  }

  if (window.kakao?.maps) {
    return Promise.resolve(window.kakao);
  }

  if (sdkPromise) {
    return sdkPromise;
  }

  sdkPromise = new Promise((resolve, reject) => {
    const appKey = process.env.NEXT_PUBLIC_KAKAO_JS_KEY;
    if (!appKey) {
      sdkPromise = null;
      reject(new Error("NEXT_PUBLIC_KAKAO_JS_KEY 환경변수가 설정되지 않았습니다"));
      return;
    }

    const script = document.createElement("script");
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${appKey}&autoload=false&libraries=services,clusterer`;
    script.async = true;
    script.onerror = () => {
      sdkPromise = null;
      reject(new Error("카카오맵 SDK 로드에 실패했습니다"));
    };
    script.onload = () => {
      window.kakao.maps.load(() => resolve(window.kakao));
    };
    document.head.appendChild(script);
  });

  return sdkPromise;
}
