package GUI
{
   import core.Base;
   import core.Constants;
   import core.Utils;
   import core.isoengine.IsoUnit;
   import flash.display.Loader;
   import flash.display.MovieClip;
   import flash.display.Shape;
   import flash.events.Event;
   import flash.events.EventDispatcher;
   import flash.events.IOErrorEvent;
   import flash.events.TimerEvent;
   import flash.geom.Rectangle;
   import flash.net.URLRequest;
   import flash.utils.Timer;
   import flash.utils.getDefinitionByName;
   import org.osflash.signals.Signal;
   
   public class AnimatedUnit
   {
      
      private const ANIM_CYCLE:int = 3000;
      
      private const MASK_MARGIN:int = 8;
      
      private const MAX_SCALE:Number = 1;
      
      private var img_name:String;
      
      private var id:int;
      
      private var anchor:MovieClip;
      
      private var thumbHeight:int;
      
      private var thumbWidth:int;
      
      private var orientation:int;
      
      private var doMask:Boolean;
      
      private var dontMove:Boolean;
      
      private var animationId:int = 1;
      
      private var anim:MovieClip;
      
      public var dispatcher:EventDispatcher;
      
      public var loaded:Boolean;
      
      private var timerAnim:Timer;
      
      private var holder:MovieClip;
      
      private var loader:Loader;
      
      private var offsetX:Number;
      
      private var offsetY:Number;
      
      private var maxScale:Number;
      
      public var sigAnimLoaded:Signal;
      
      public var sigAnimLoadError:Signal;
      
      private var removed:Boolean = false;
      
      public function AnimatedUnit(param1:MovieClip, param2:String, param3:int, param4:int, param5:int = -1, param6:int = 4, param7:Boolean = true, param8:Number = 0, param9:Number = 0, param10:Boolean = false, param11:Number = 1)
      {
         var _loc12_:* = null;
         this.sigAnimLoaded = new Signal(MovieClip);
         this.sigAnimLoadError = new Signal(IOErrorEvent);
         super();
         this.dispatcher = new EventDispatcher();
         this.loaded = false;
         this.img_name = param2;
         this.id = param5;
         this.anchor = param1;
         this.offsetX = param8;
         this.offsetY = param9;
         this.maxScale = param11;
         if(this.anchor.thumb != null)
         {
            this.holder = this.anchor.thumb;
         }
         else
         {
            this.holder = this.anchor;
         }
         this.thumbWidth = param3;
         this.thumbHeight = param4;
         this.orientation = param6;
         this.doMask = param7;
         this.dontMove = param10;
         var _loc13_:Object = Base.Main.sheetObject;
         if(this.id != -1 && _loc13_[this.id] != null)
         {
            trace("sheetobject exists for:" + param2);
            this.anim = new _loc13_[this.id]();
            this.loaded = true;
            this.previewAnimationLoaded();
         }
         else
         {
            this.loader = new Loader();
            Loader(this.loader).contentLoaderInfo.addEventListener(Event.COMPLETE,this.previewAnimationLoaded);
            _loc12_ = Base.Main.apfx + "buildingsprites/" + param2 + ".swf";
            trace("LOADING: " + _loc12_);
            Loader(this.loader).load(new URLRequest(_loc12_));
            Loader(this.loader).contentLoaderInfo.addEventListener(IOErrorEvent.IO_ERROR,this.onLoaderError);
         }
      }
      
      public function set animation(param1:int) : void
      {
         this.animationId = param1;
      }
      
      public function remove() : void
      {
         this.removed = true;
         if(this.loader != null)
         {
            Loader(this.loader).contentLoaderInfo.removeEventListener(Event.COMPLETE,this.previewAnimationLoaded);
            try
            {
               Loader(this.loader).close();
            }
            catch(e:Error)
            {
            }
            if(this.loader.parent != null)
            {
               this.loader.parent.removeChild(this.loader);
            }
         }
         else if(this.anim != null)
         {
            this.holder.removeChild(this.anim);
         }
      }
      
      protected function onLoaderError(param1:IOErrorEvent) : void
      {
         trace("AnimatedUnit Load Error");
         this.sigAnimLoadError.dispatch(param1);
      }
      
      private function previewAnimationLoaded(param1:Event = null) : void
      {
         var _loc2_:Class = null;
         var _loc8_:Rectangle = null;
         var _loc9_:Shape = null;
         if(this.removed)
         {
            this.loader = null;
            return;
         }
         if(param1 != null)
         {
            this.anim = param1.currentTarget.loader.content.getChildAt(0);
            _loc2_ = Class(param1.currentTarget.applicationDomain.getDefinition(this.img_name));
            Base.Main.addDinamicallyLoadedAsset(_loc2_,this.id);
            this.loader = null;
         }
         this.anim.gotoAndStop(this.animationId * 5 + IsoUnit.directionFrame(this.orientation));
         var _loc3_:Rectangle = Utils.getVisibleBounds(this.anim);
         var _loc4_:Number = this.thumbWidth / _loc3_.width;
         var _loc5_:Number = this.thumbHeight / _loc3_.height;
         var _loc6_:Number = Math.min(_loc4_,_loc5_);
         if(_loc6_ > this.maxScale)
         {
            _loc6_ = this.maxScale;
         }
         var _loc7_:Number = IsoUnit.directionScaleX(this.orientation);
         this.anim.scaleX = _loc6_ * _loc7_;
         this.anim.scaleY = _loc6_;
         _loc8_ = this.anim.getBounds(this.anim);
         if(_loc7_ < 0)
         {
            _loc8_.x = -_loc8_.right;
         }
         if(this.dontMove)
         {
            this.anim.x = 0;
            this.anim.y = 0;
         }
         else
         {
            this.anim.x = -_loc8_.left * _loc6_ + (this.thumbWidth - _loc8_.width * _loc6_) / 2;
            this.anim.y = -_loc8_.top * _loc6_ + (this.thumbHeight - _loc8_.height * _loc6_) / 2;
         }
         this.anim.x += this.offsetX;
         this.anim.y += this.offsetY;
         if(this.doMask)
         {
            _loc9_ = new Shape();
            _loc9_.graphics.beginFill(0,0.5);
            _loc9_.graphics.drawRect(-this.MASK_MARGIN,-this.MASK_MARGIN,this.thumbWidth + this.MASK_MARGIN * 2,this.thumbHeight + this.MASK_MARGIN * 2);
            _loc9_.graphics.endFill();
            this.anim.mask = _loc9_;
            this.holder.addChild(_loc9_);
         }
         this.holder.addChild(this.anim);
         this.dispatcher.dispatchEvent(new Event(Event.COMPLETE));
         this.sigAnimLoaded.dispatch(this.anim);
      }
      
      public function get animClip() : MovieClip
      {
         return this.anim;
      }
      
      private function timerTick(param1:TimerEvent) : void
      {
         var e:TimerEvent = param1;
         try
         {
            this.cycleAnimation();
         }
         catch(e:Error)
         {
         }
      }
      
      protected function cycleAnimation() : void
      {
         var _loc1_:MovieClip = MovieClip(this.holder.getChildAt(0));
         var _loc2_:int = IsoUnit.directionFrame(this.orientation);
         if(_loc1_.currentFrame == Constants.ANIMATION_WALKING * 5 + _loc2_)
         {
            _loc1_.gotoAndStop(Constants.ANIMATION_ATTACKING * 5 + _loc2_);
            if(_loc1_.numChildren > 0)
            {
               MovieClip(_loc1_.getChildAt(0)).play();
            }
         }
         else if(_loc1_.currentFrame == Constants.ANIMATION_ATTACKING * 5 + _loc2_ && _loc1_.totalFrames >= Constants.ANIMATION_ATTACKING_SPECIAL1 * 5)
         {
            _loc1_.gotoAndStop(Constants.ANIMATION_ATTACKING_SPECIAL1 * 5 + _loc2_);
         }
         else
         {
            _loc1_.gotoAndStop(Constants.ANIMATION_WALKING * 5 + _loc2_);
         }
      }
   }
}

